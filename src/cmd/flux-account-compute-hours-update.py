#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
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
from fluxacct.accounting import sql_util as sql


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

    # check version of database; if not up to date, output message and exit
    if sql.db_version(conn) < fluxacct.accounting.DB_SCHEMA_VERSION:
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
    associations = []

    # fetch all rows from association_table (will print out tuples)
    for row in cur.execute(
        """SELECT userid, username, bank, default_bank
           FROM association_table"""
    ):
        # create a JSON payload with the results of the query
        association = {
            "userid": int(row["userid"]),
            "username": str(row["username"]),
            "bank": str(row["bank"]),
            "default_bank": str(row["default_bank"]),
        }
        associations.append(association)

    data = {"data": associations}

    flux.Flux().rpc("job-manager.compute_hours_limits.update", json.dumps(data)).get()

    # close DB connection
    cur.close()
    conn.close()


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
        "username": owner_username,
        "bank": owner_username,
        "default_bank": owner_username,
    }

    flux.Flux().rpc(
        "job-manager.compute_hours_limits.update",
        json.dumps({"data": [instance_owner_data]}),
    ).get()


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Send a bulk update of association information from a
        flux-accounting database to the compute hours limits plugin.
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
