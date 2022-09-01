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
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u


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


def populate_db(path, users=None, banks=None):
    conn = est_sqlite_conn(path)
    cur = conn.cursor()

    if banks is not None:
        try:
            with open(banks) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=",")

                for row in csv_reader:
                    b.add_bank(
                        conn,
                        bank=row[0],
                        parent_bank=row[1],
                        shares=row[2],
                    )
        except IOError as err:
            print(err)

    if users is not None:
        try:
            with open(users) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=",")

                # assign default values to fields if
                # their slot is empty in the csv file
                for row in csv_reader:
                    username = row[0]
                    uid = row[1]
                    bank = row[2]
                    shares = row[3] if row[3] != "" else 1
                    max_running_jobs = row[4] if row[4] != "" else 5
                    max_active_jobs = row[5] if row[5] != "" else 7
                    max_nodes = row[6] if row[6] != "" else 5
                    queues = row[7]

                    u.add_user(
                        conn,
                        username,
                        bank,
                        uid,
                        shares,
                        max_running_jobs,
                        max_active_jobs,
                        max_nodes,
                        queues,
                    )
        except IOError as err:
            print(err)


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Populate a flux-accounting database with a .csv file.

        Order of elements required for populating association_table:

        Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues

        [Shares], [MaxRunningJobs], [MaxActiveJobs], and [MaxNodes] can be left
        blank ('') in the .csv file for a given row.

        ----------------

        Order of elements required for populating bank_table:

        Bank,ParentBank,Shares

        [ParentBank] can be left blank ('') in .csv file for a given row.
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

    populate_db(path, args.users, args.banks)


if __name__ == "__main__":
    main()
