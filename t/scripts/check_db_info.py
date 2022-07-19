#!/usr/bin/env python3
###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sqlite3
import sys
import argparse
import os

from argparse import RawDescriptionHelpFormatter


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


def check_tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    for table in tables:
        print(table[0])


def check_columns(cur, table_name):
    print("table name:", table_name)
    # get the information of each column in the table from new DB
    cur.execute("PRAGMA table_info(%s)" % table_name)
    columns = cur.fetchall()
    for col in columns:
        print(col[1])


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Check the tables in a DB and/or the columns in a table in a DB.
        """,
        formatter_class=RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-p", "--path", dest="db_path", help="specify location of database file"
    )
    parser.add_argument(
        "-t",
        nargs="?",
        const=True,
        dest="table",
        help="check tables of database",
    )
    parser.add_argument(
        "-c",
        dest="table_name",
        help="check columns of TABLE",
    )

    args = parser.parse_args()

    conn = est_sqlite_conn(args.db_path)
    cur = conn.cursor()

    if args.table:
        check_tables(cur)
    if args.table_name:
        check_columns(cur, args.table_name)

    conn.close()


if __name__ == "__main__":
    main()
