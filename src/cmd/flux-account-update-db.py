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
import tempfile
import shutil

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
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(1)

    return conn


# gets a final list of columns for the new version of a table, which
# include any columns added in a newer version or removed from an older version
def get_cols_list(old_columns, new_columns):
    # create a list of just the column names for comparison
    old_columns_names = [column[1] for column in old_columns]
    new_columns_names = [column[1] for column in new_columns]
    cols = []

    for column in new_columns:
        if column[1] in old_columns_names and column[1] in new_columns_names:
            cols.append(column)
        elif column[1] in new_columns_names:
            cols.append(column)

    return cols


# adds a new version of the table to the DB
def add_tmp_table_to_db(old_cur, table, cols):
    add_stmt = "CREATE TABLE IF NOT EXISTS " + table[0] + "_tmp" + " ("

    for column in cols:
        column_name = column[1]
        column_type = column[2]
        not_null = column[3]
        default_value = column[4]

        add_stmt += column_name + " " + column_type + " "
        if default_value is not None:
            add_stmt += "DEFAULT " + default_value
        if not_null == 1:
            add_stmt += " NOT NULL"
        # only add a comma if column is not last item in list
        if column != cols[-1]:
            add_stmt += ", "

    # look for primary key to add to table; if column[5] > 0, that means
    # it is either the primary key or one of the values that make up a
    # primary key
    primary_keys = ",".join([column[1] for column in cols if column[5] > 0])
    if len(primary_keys) > 0:
        add_stmt += ", PRIMARY KEY ("
        add_stmt += ",".join([column[1] for column in cols if column[5] > 0])
        add_stmt += ")"

    add_stmt += ");"

    # add new table to DB
    old_cur.execute(add_stmt)


# move all existing rows from the old version of the table to the new version of the table
def move_existing_rows(old_cur, cols, old_columns, table):
    # convert old_columns and cols to just lists of column names instead of tuples
    old_columns = [column[1] for column in old_columns]
    cols = [column[1] for column in cols]

    # get list of columns to be added to new table that were in old table but not new table
    existing_cols = [column for column in cols if column in old_columns]
    insert = "INSERT INTO " + table[0] + "_tmp"
    values = " (" + (",".join(existing_cols)) + ")"
    select = " SELECT " + (",".join(existing_cols)) + " FROM " + table[0]
    final_stmt = insert + values + select

    old_cur.execute(final_stmt)


# drops the '_tmp' appended to the new version of the table to match the old table name
def rename_tmp_table(old_cur, table):
    # drop old table
    drop_stmt = "DROP TABLE " + table[0]
    old_cur.execute(drop_stmt)

    # rename table to match old table
    alter_stmt = "ALTER TABLE " + table[0] + "_tmp" + " RENAME TO " + table[0]
    old_cur.execute(alter_stmt)


# update_tables() is responsible for adding any new tables that don't yet exist
# in the old flux-accounting DB. It will look at the table schema for the table
# that doesn't yet exist and create a "CREATE TABLE ..." statement to add to the
# old flux-accounting DB
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


# update_columns() looks that the existing tables in the old flux-accounting DB
# to see if any of the tables need to add any additional columns to its tables.
# If it does, it will create a new version of the table with any added or removed
# columns from a newer version of flux-accounting, copy any and all existing rows
# from the old table, and DROP the old table to be replaced with the new table
def update_columns(old_conn, old_cur, new_cur):
    print("checking for new columns to add in tables...")

    # get all table names from the temporary new database
    new_cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    new_tables = new_cur.fetchall()

    for table in new_tables:
        # get the information of each column in the table from new DB
        new_cur.execute("PRAGMA table_info(%s)" % table)
        new_columns = new_cur.fetchall()

        # get the information of each column in the same table from old DB
        old_cur.execute("PRAGMA table_info(%s)" % table)
        old_columns = old_cur.fetchall()

        # generate a final columns list, which consist of columns added
        # in a newer version or removed from an older version
        cols = get_cols_list(old_columns, new_columns)

        # create a new version of table with the updated column list
        add_tmp_table_to_db(old_cur, table, cols)

        # move elements from the old table to new version of the table
        move_existing_rows(old_cur, cols, old_columns, table)

        # rename the new table to match the name of the old table
        rename_tmp_table(old_cur, table)


def update_db(path, new_db):
    old_conn = est_sqlite_conn(path)
    old_cur = old_conn.cursor()

    try:
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # we should only pass a new DB if we are testing the flux
            # account-update-db command; normally, no value should be passed for
            # new_db
            if not new_db:
                tmp_db_path = tmp_dir_name + "/tmpFluxAccounting.db"
                c.create_db(tmp_db_path)

                new_conn = sqlite3.connect("file:%s?mode=rw" % (tmp_db_path), uri=True)
            else:
                new_conn = sqlite3.connect("file:%s?mode=rw" % new_db, uri=True)

            new_cur = new_conn.cursor()

            update_tables(old_conn, old_cur, new_cur)

            update_columns(old_conn, old_cur, new_cur)

            # update user_version for DB
            old_cur.execute(
                "PRAGMA user_version = %d" % (fluxacct.accounting.db_schema_version)
            )

            # commit changes
            old_conn.commit()

            # close connections to DB's and remove temporary database
            old_conn.close()
            new_conn.close()
    except sqlite3.OperationalError as exc:
        print(f"Unable to open temporary database file: {new_db}")
        print(f"Exception: {exc}")
        shutil.rmtree(tmp_dir_name)
        sys.exit(1)
    except sqlite3.IntegrityError as exc:
        print(f"Exception: {exc}")
        shutil.rmtree(tmp_dir_name)
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
