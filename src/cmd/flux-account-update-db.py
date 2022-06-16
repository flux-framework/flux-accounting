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
import argparse
import os
import sqlite3
import sys

from argparse import RawDescriptionHelpFormatter

import fluxacct.accounting
from fluxacct.accounting import create_db as c


def set_db_loc(args):
    path = args.old_db if args.old_db else fluxacct.accounting.db_path

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


# update_tables() is responsible for adding any new tables that don't yet exist
# in the old flux-accounting DB. It will look at the table schema for the table
# that doesn't yet exist and create a "CREATE TABLE ..." statement to add and
# commit to the old flux-accounting DB
def update_tables(old_conn, old_cur, new_cur):
    print("checking for new tables...")

    # get all tables from old database
    old_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    old_tables = old_cur.fetchall()

    # get all tables from the temporary new database
    new_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    new_tables = new_cur.fetchall()

    for table in new_tables:
        if table not in old_tables:
            # we need to add this table to the DB
            print("new table found: %s" % table[0])

            # get schema information about new table to add
            new_cur.execute("PRAGMA table_info(%s)" % table)
            new_columns = new_cur.fetchall()

            add_stmt = "CREATE TABLE IF NOT EXISTS " + table[0] + "("

            for column in new_columns:
                column_name = column[1]
                column_type = column[2]
                not_null = column[3]
                default_value = column[4]

                add_stmt += column_name + " " + column_type + " "
                if default_value is not None:
                    add_stmt += "DEFAULT " + default_value + " "
                if not_null == 1:
                    add_stmt += "NOT NULL, "

            # look for primary key in new table to add
            for column in new_columns:
                if column[5] == 1:
                    add_stmt += "PRIMARY KEY (" + column[1] + "));"

            # add table to old DB
            old_cur.execute(add_stmt)
            old_conn.commit()


# update_columns() looks that the existing tables in the old flux-accounting DB
# to see if any of the tables need to add any additional columns to its tables.
# If it does, it will issue an "ALTER TABLE ..." statement to add any columns
def update_columns(old_conn, old_cur, new_cur):
    print("checking for new columns to add in tables...")

    # get all table names from the temporary new database
    new_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    new_tables = new_cur.fetchall()

    for table in new_tables:
        # get the information of each column in the table from new DB
        new_cur.execute("PRAGMA table_info(%s)" % table)
        new_columns = new_cur.fetchall()

        # get the information of each column in the same table from old DB
        old_cur.execute("PRAGMA table_info(%s)" % table)
        old_columns = old_cur.fetchall()

        for column in new_columns:
            if column not in old_columns:
                # we need to add this column to the DB
                print("new column found in %s: %s" % (table[0], column[1]))

                # we need to add this column to the table in the old DB
                alter_stmt = "ALTER TABLE " + table[0] + " ADD COLUMN "
                column_name = column[1]
                column_type = column[2]
                not_null = column[3]
                default_value = column[4]

                alter_stmt += column_name + " " + column_type
                if default_value is not None:
                    alter_stmt += " DEFAULT " + default_value
                if not_null == 1:
                    alter_stmt += " NOT NULL"

                old_cur.execute(alter_stmt)
                # commit changes
                old_conn.commit()


def update_db(path, new_db):
    old_conn = est_sqlite_conn(path)
    old_cur = old_conn.cursor()

    try:
        # we should only pass a new DB if we are testing the flux
        # account-update-db command; normally, no value should be passed for
        # new_db
        if not new_db:
            new_db = "tmpFluxAccounting.db"
            c.create_db(new_db)

        new_conn = sqlite3.connect("file:%s?mode=rw" % new_db, uri=True)
        new_cur = new_conn.cursor()

        update_tables(old_conn, old_cur, new_cur)

        update_columns(old_conn, old_cur, new_cur)

        # close connections to DB's and remove temporary database
        old_conn.close()
        new_conn.close()

        os.remove(new_db)
    except sqlite3.OperationalError:
        print(f"Unable to open temporary database file: %s" % new_db)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Update a flux-accounting database with any new tables or
        columns in any of the existing tables.
        """,
        formatter_class=RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-p", "--path", dest="old_db", help="specify location of database file"
    )
    parser.add_argument(
        "-n",
        "--new-db",
        dest="new_db",
        help="(testing only) specify location of new template database file",
    )

    args = parser.parse_args()

    old_db = set_db_loc(args)

    update_db(old_db, args.new_db)


if __name__ == "__main__":
    main()
