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
    except sqlite3.OperationalError:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
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
                    max_jobs = row[4] if row[4] != "" else 5
                    qos = row[5]

                    u.add_user(
                        conn,
                        username,
                        bank,
                        uid,
                        shares,
                        max_jobs,
                        qos,
                    )
        except IOError as err:
            print(err)


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Populate a flux-accounting database with a .csv file.

        Order of elements required for populating association_table:

        Username,UserID,Bank,Shares,MaxJobs,QOS

        [Shares] and [MaxJobs] can be left blank ('') in .csv file for a given row.

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
