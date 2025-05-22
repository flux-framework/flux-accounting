#!/usr/bin/env python3

###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import argparse
import sys
import os
import sqlite3
import json
import subprocess
import pwd

import flux

import fluxacct.accounting


def set_db_loc(args):
    path = args.path if args.path else fluxacct.accounting.DB_PATH

    return path


def est_sqlite_conn(path):
    # try to open database file; will exit with -1 if database file not found
    if not os.path.isfile(path):
        print(f"Database file does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        # set foreign keys constraint
        conn.execute("PRAGMA foreign_keys = 1")
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(1)

    # check version of database; if not up to date, output message
    # and exit
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    db_version = cur.fetchone()[0]
    if db_version < fluxacct.accounting.DB_SCHEMA_VERSION:
        print(
            """flux-accounting database out of date; updating DB with """
            """'flux account-update-db' before sending information to plugin"""
        )
        # if flux account-update-db fails, we should not attempt to send data from
        # the DB to the priority plugin, and instead we should abort
        try:
            subprocess.run(["flux", "account-update-db", "-p", path], check=True)
        except SystemExit as exc:
            print(f"Exception: {exc.code}")
            sys.exit(1)

    return conn


def bulk_update(path):
    conn = est_sqlite_conn(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    data = {}
    bulk_user_data = []
    bulk_q_data = []
    bulk_proj_data = []
    bulk_bank_data = []

    # fetch all rows from association_table (will print out tuples)
    for row in cur.execute(
        """SELECT userid, bank, default_bank,
           fairshare, max_running_jobs, max_active_jobs,
           queues, active, projects, default_project, max_nodes, max_cores
           FROM association_table"""
    ):
        # create a JSON payload with the results of the query
        single_user_data = {
            "userid": int(row["userid"]),
            "bank": str(row["bank"]),
            "def_bank": str(row["default_bank"]),
            "fairshare": float(row["fairshare"]),
            "max_running_jobs": int(row["max_running_jobs"]),
            "max_active_jobs": int(row["max_active_jobs"]),
            "queues": str(row["queues"]),
            "active": int(row["active"]),
            "projects": str(row["projects"]),
            "def_project": str(row["default_project"]),
            "max_nodes": int(row["max_nodes"]),
            "max_cores": int(row["max_cores"]),
        }
        bulk_user_data.append(single_user_data)

    data = {"data": bulk_user_data}

    flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(data)).get()

    # fetch all rows from queue_table
    for row in cur.execute("SELECT * FROM queue_table"):
        # create a JSON payload with the results of the query
        single_q_data = {
            "queue": str(row["queue"]),
            "min_nodes_per_job": int(row["min_nodes_per_job"]),
            "max_nodes_per_job": int(row["max_nodes_per_job"]),
            "max_time_per_job": int(row["max_time_per_job"]),
            "priority": int(row["priority"]),
            "max_running_jobs": int(row["max_running_jobs"]),
        }
        bulk_q_data.append(single_q_data)

    data = {"data": bulk_q_data}

    flux.Flux().rpc("job-manager.mf_priority.rec_q_update", json.dumps(data)).get()

    # fetch all rows from project_table
    for row in cur.execute("SELECT project FROM project_table"):
        # create a JSON payload with the results of the query
        single_project = {
            "project": str(row["project"]),
        }
        bulk_proj_data.append(single_project)

    data = {"data": bulk_proj_data}
    flux.Flux().rpc("job-manager.mf_priority.rec_proj_update", data).get()

    # fetch rows from bank_table
    for row in cur.execute("SELECT bank, priority FROM bank_table"):
        single_bank = {
            "bank": str(row["bank"]),
            "priority": float(row["priority"]),
        }
        bulk_bank_data.append(single_bank)

    data = {"data": bulk_bank_data}
    flux.Flux().rpc("job-manager.mf_priority.rec_bank_update", data).get()

    flux.Flux().rpc("job-manager.mf_priority.reprioritize")

    # close DB connection
    cur.close()


def send_instance_owner_info():
    handle = flux.Flux()
    # get uid, username of instance owner
    owner_uid = handle.attr_get("security.owner")
    try:
        # look up corresponding username of instance owner
        owner_info = pwd.getpwuid(int(owner_uid))
        owner_username = owner_info.pw_name
    except KeyError:
        # can't find instance owner info; set username to the uid
        owner_username = owner_uid

    # construct instance owner dictionary
    instance_owner_data = {
        "userid": int(owner_uid),
        "bank": owner_username,
        "def_bank": owner_username,
        "fairshare": 0.5,
        "max_running_jobs": 1000000,
        "max_active_jobs": 1000000,
        "queues": "",
        "active": 1,
        "projects": "*",
        "def_project": "*",
        "max_nodes": 1000000,
        "max_cores": 1000000,
    }

    flux.Flux().rpc(
        "job-manager.mf_priority.rec_update",
        json.dumps({"data": [instance_owner_data]}),
    ).get()


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Send a bulk update of user information from a
        flux-accounting database to the multi-factor priority plugin.
        """
    )

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    args = parser.parse_args()

    path = set_db_loc(args)

    bulk_update(path)
    send_instance_owner_info()


if __name__ == "__main__":
    main()
