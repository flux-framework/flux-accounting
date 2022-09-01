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
import csv
import os
import sqlite3
import sys

from argparse import RawDescriptionHelpFormatter

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
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(1)

    return conn


def export_db_info(path, users=None, banks=None):
    conn = est_sqlite_conn(path)
    cur = conn.cursor()

    try:
        select_users_stmt = """
            SELECT username, userid, bank, shares, max_running_jobs, max_active_jobs,
            max_nodes, queues FROM association_table
        """
        cur.execute(select_users_stmt)
        table = cur.fetchall()

        # open a .csv file for writing
        users_filepath = users if users else "users.csv"
        users_file = open(users_filepath, "w")
        with users_file:
            writer = csv.writer(users_file)

            for row in table:
                writer.writerow(row)

        select_banks_stmt = """
            SELECT bank, parent_bank, shares FROM bank_table
        """
        cur.execute(select_banks_stmt)
        table = cur.fetchall()

        banks_filepath = banks if banks else "banks.csv"
        banks_file = open(banks_filepath, "w")
        with banks_file:
            writer = csv.writer(banks_file)

            for row in table:
                writer.writerow(row)
    except IOError as err:
        print(err)


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Extract flux-accounting database information into two .csv files.

        Order of columns extracted from association_table:

        Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues

        If no custom path is specified, this will create a file in the
        current working directory called users.csv.

        ----------------

        Order of columns extracted from bank_table:

        Bank,ParentBank,Shares

        If no custom path is specified, this will create a file in the
        current working directory called banks.csv.

        Use these two files to populate a new flux-accounting DB with:

        flux account-pop-db -p path/to/db -b banks.csv -u users.csv
        """,
        formatter_class=RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    parser.add_argument(
        "-u", "--users", help="path to a .csv file containing user information"
    )
    parser.add_argument(
        "-b", "--banks", help="path to a .csv file containing bank information"
    )

    args = parser.parse_args()

    path = set_db_loc(args)

    export_db_info(path, args.users, args.banks)


if __name__ == "__main__":
    main()
