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
import sqlite3
import time

import pandas as pd


def add_bank(conn, bank, shares, parent_bank=""):
    # if the parent bank is not "", that means the bank
    # trying to be added wants to be placed under a parent bank
    if parent_bank != "":
        try:
            select_stmt = "SELECT shares FROM bank_table where bank=?"
            dataframe = pd.read_sql_query(select_stmt, conn, params=(parent_bank,))
            # if length of dataframe is 0, that means the parent bank wasn't found
            if len(dataframe.index) == 0:
                raise Exception("Parent bank not found in bank table")
        except pd.io.sql.DatabaseError as e_database_error:
            print(e_database_error)

    # insert the bank values into the database
    try:
        conn.execute(
            """
            INSERT INTO bank_table (
                bank,
                parent_bank,
                shares
            )
            VALUES (?, ?, ?)
            """,
            (bank, parent_bank, shares),
        )
        # commit changes
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def view_bank(conn, bank):
    try:
        # get the information pertaining to a bank in the Accounting DB
        select_stmt = "SELECT * FROM bank_table where bank=?"
        dataframe = pd.read_sql_query(select_stmt, conn, params=(bank,))
        # if the length of dataframe is 0, that means
        # the bank specified was not found in the table
        if len(dataframe.index) == 0:
            print("Bank not found in bank_table")
        else:
            print(dataframe)
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def delete_bank(conn, bank):
    try:
        # delete the first bank passed in
        delete_stmt = """
            DELETE FROM bank_table
            WHERE bank=?
            """
        cursor = conn.cursor()
        cursor.execute(delete_stmt, (bank,))

        # construct a DataFrame object out of the
        # bank passed in
        df = pd.DataFrame([bank], columns=["bank"])
        bank = df.iloc[0]

        # helper function to traverse the bank table
        # and delete all of its sub banks
        def get_sub_banks(row):
            select_stmt = """
                SELECT bank
                FROM bank_table
                WHERE parent_bank=?
                """
            cursor = conn.cursor()
            dataframe = pd.read_sql_query(select_stmt, conn, params=(row["bank"],))

            # we've reached a bank with no sub banks
            if len(dataframe) == 0:
                select_associations_stmt = """
                    SELECT username, bank
                    FROM association_table
                    WHERE bank=?
                    """
                for row in cursor.execute(select_associations_stmt, (row["bank"],)):
                    delete_user(conn, user=row[0], bank=row[1])
            # else, delete all of its sub banks and continue
            # traversing
            else:
                for index, sub_bank_row in dataframe.iterrows():
                    cursor.execute(delete_stmt, (sub_bank_row["bank"],))
                    get_sub_banks(sub_bank_row)

        get_sub_banks(bank)
    # if an exception occcurs while recursively deleting
    # the parent banks, then throw the exception and roll
    # back the changes made to the DB
    except sqlite3.OperationalError as e:
        print(e)
        conn.rollback()
        return 1

    # commit changes
    conn.commit()


def edit_bank(conn, bank, shares):
    print(shares)
    # if user tries to edit a shares value <= 0,
    # raise an exception
    if shares <= 0:
        raise Exception("New shares amount must be >= 0")
    try:
        # edit value in bank_table
        conn.execute(
            "UPDATE bank_table SET shares=? WHERE bank=?",
            (
                shares,
                bank,
            ),
        )
        # commit changes
        conn.commit()
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def view_user(conn, user):
    try:
        # get the information pertaining to a user in the Accounting DB
        select_stmt = "SELECT * FROM association_table where username=?"
        dataframe = pd.read_sql_query(select_stmt, conn, params=(user,))
        # if the length of dataframe is 0, that means
        # the user specified was not found in the table
        if len(dataframe.index) == 0:
            print("User not found in association_table")
        else:
            print(dataframe)
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def add_user(conn, username, bank, admin_level=1, shares=1, max_jobs=1, max_wall_pj=60):

    try:
        # insert the user values into association_table
        conn.execute(
            """
            INSERT INTO association_table (
                creation_time,
                mod_time,
                deleted,
                username,
                admin_level,
                bank,
                shares,
                max_jobs,
                max_wall_pj
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                0,
                username,
                admin_level,
                bank,
                shares,
                max_jobs,
                max_wall_pj,
            ),
        )
        # commit changes
        conn.commit()
        # insert the user values into job_usage_factor_table
        conn.execute(
            """
            INSERT INTO job_usage_factor_table (
                username,
                bank
            )
            VALUES (?, ?)
            """,
            (
                username,
                bank,
            ),
        )
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def delete_user(conn, user, bank):
    # delete user account from association_table
    delete_stmt = "DELETE FROM association_table WHERE username=? AND bank=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (user, bank,))
    # commit changes
    conn.commit()


def edit_user(conn, username, field, new_value):
    fields = [
        "username",
        "admin_level",
        "bank",
        "shares",
        "max_jobs",
        "max_wall_pj",
    ]
    try:
        if field in fields:
            the_field = field

            # edit value in accounting database
            conn.execute(
                "UPDATE association_table SET " + the_field + "=? WHERE username=?",
                (
                    new_value,
                    username,
                ),
            )
            # commit changes
            conn.commit()
        else:
            raise ValueError("Field not found in association table")
    except Exception as e:
        print(e)
