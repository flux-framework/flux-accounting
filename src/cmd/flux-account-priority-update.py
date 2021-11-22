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

import flux

import fluxacct.accounting


def set_db_loc(args):
    path = args.path if args.path else fluxacct.accounting.db_path

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
    except sqlite3.OperationalError:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        sys.exit(1)

    return conn


def bulk_update(path):
    conn = est_sqlite_conn(path)
    cur = conn.cursor()

    data = {}
    bulk_user_data = []

    # fetch all rows from association_table (will print out tuples)
    for row in cur.execute(
        "SELECT userid, bank, default_bank, fairshare, max_jobs FROM association_table"
    ):
        # create a JSON payload with the results of the query
        single_user_data = {
            "userid": int(row[0]),
            "bank": str(row[1]),
            "def_bank": str(row[2]),
            "fairshare": float(row[3]),
            "max_jobs": int(row[4]),
        }
        bulk_user_data.append(single_user_data)

    data = {"data": bulk_user_data}

    flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(data)).get()


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


if __name__ == "__main__":
    main()
