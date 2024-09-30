#!/usr/bin/env python3

###############################################################
# Copyright 2023 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################

import os
import sys
import argparse
import sqlite3
import json

import flux
import flux.job
import fluxacct.accounting


def set_db_loc(args):
    path = args.path if args.path else fluxacct.accounting.db_path

    return path


# try to open database file; will exit with 1 if database file not found
def est_sqlite_conn(path):
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

    return conn


def get_jobs(rpc_handle):
    try:
        jobs = rpc_handle.get_jobs()
        return jobs
    except EnvironmentError as exc:
        print("{}: {}".format("rpc", exc.strerror), file=sys.stderr)
        sys.exit(1)


# fetch new jobs using Flux's job-list and job-info interfaces;
# create job records for each newly seen job
def fetch_new_jobs(last_timestamp=0.0):
    handle = flux.Flux()

    # attributes needed using job-list
    custom_attrs = ["userid", "t_submit", "t_run", "t_inactive", "ranks"]

    # construct and send RPC
    rpc_handle = flux.job.job_list_inactive(
        handle, attrs=custom_attrs, since=last_timestamp
    )
    jobs = get_jobs(rpc_handle)

    # job_records is a list of dictionaries where each dictionary contains
    # information about a single job record
    job_records = []
    for single_job in jobs:
        single_record = {}
        # get attributes from job-list
        for attr in single_job:
            single_record[attr] = single_job[attr]

        # attributes needed using job-info
        data = flux.job.job_kvs_lookup(
            handle, single_job["id"], keys=["R", "jobspec"], decode=False
        )

        if data is None:
            # this job never ran; don't add it to a user's list of job records
            continue
        if data["R"] is not None:
            single_record["R"] = data["R"]
        if data["jobspec"] is not None:
            single_record["jobspec"] = data["jobspec"]
            try:
                jobspec = json.loads(single_record["jobspec"])
                # using .get() here ensures no KeyError is raised if
                # "attributes" or "project" are missing; will set
                # single_record["project"] to None if it can't be found
                accounting_attributes = jobspec.get("attributes", {}).get("system", {})
                single_record["project"] = accounting_attributes.get("project")
            except json.JSONDecodeError as exc:
                # the job does not have a project in jobspec, so don't add it
                # to the job dictionary
                continue

        required_keys = [
            "userid",
            "t_submit",
            "t_run",
            "t_inactive",
            "ranks",
            "id",
            "R",
            "jobspec",
        ]
        if not all(
            key in single_record and single_record.get(key) is not None
            for key in required_keys
        ):
            # job does not have all required fields to be added to jobs table
            # in DB; skip this entry
            continue

        # append job to job_records list
        job_records.append(single_record)

    return job_records


# insert newly seen jobs into the "jobs" table in the flux-accounting DB
def insert_jobs_in_db(conn, job_records):
    cur = conn.cursor()

    for single_job in job_records:
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO jobs
                (id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, project)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    single_job["id"],
                    single_job["userid"],
                    single_job["t_submit"],
                    single_job["t_run"],
                    single_job["t_inactive"],
                    single_job["ranks"],
                    single_job["R"],
                    single_job["jobspec"],
                    single_job["project"]
                    if single_job.get("project") is not None
                    else "",
                ),
            )
        except KeyError:
            # one of the key-value pairs is missing or invalid; skip the entry
            continue

    conn.commit()


# connect to flux-core's job-archive DB, fetch all records from its jobs table,
# and populate them into the jobs table of the flux-accounting DB
def copy_db_contents(old_cur, cur, conn):
    select_stmt = """
    SELECT id,userid,t_submit,t_run,t_inactive,ranks,R,jobspec FROM jobs
    """
    insert_stmt = """
    INSERT OR IGNORE INTO jobs
    (id,userid,t_submit,t_run,t_inactive,ranks,R,jobspec)
    VALUES (?,?,?,?,?,?,?,?)
    """

    old_cur.execute(select_stmt)
    result = old_cur.fetchall()

    if result:
        for row in result:
            if row[6] == "":
                # this job never ran; skip it
                continue
            cur.execute(
                insert_stmt,
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                ),
            )

        conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Fetch new job records using Flux's job-list and job-info
        interfaces and insert them into a table in the flux-accounting DB.
        """
    )

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    parser.add_argument(
        "-c", "--copy", dest="copy", help="copy contents from a job-archive DB"
    )
    args = parser.parse_args()

    path = set_db_loc(args)
    conn = est_sqlite_conn(path)
    cur = conn.cursor()

    if args.copy:
        # copy the contents from one job-archive DB to this one
        old_archive_conn = est_sqlite_conn(args.copy)
        old_cur = old_archive_conn.cursor()
        copy_db_contents(old_cur, cur, conn)

    # get the timestamp of the last seen job
    timestamp = 0.0
    cur.execute("SELECT MAX(t_inactive) FROM jobs")
    timestamp_arr = cur.fetchall()

    if timestamp_arr[0][0]:
        timestamp = timestamp_arr[0][0]

    job_records = []
    job_records = fetch_new_jobs(timestamp)

    insert_jobs_in_db(conn, job_records)


if __name__ == "__main__":
    main()
