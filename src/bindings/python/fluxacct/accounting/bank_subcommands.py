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

from fluxacct.accounting import user_subcommands as u


def add_bank(conn, bank, shares, parent_bank=""):
    cur = conn.cursor()
    # if the parent bank is not "", that means the bank
    # trying to be added wants to be placed under a parent bank
    if parent_bank != "":
        try:
            cur.execute("SELECT shares FROM bank_table WHERE bank=?", (parent_bank,))
            row = cur.fetchone()
            if row is None:
                raise Exception("Parent bank not found in bank table")
        except sqlite3.OperationalError as e_database_error:
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
    cur = conn.cursor()
    try:
        # get the information pertaining to a bank in the Accounting DB
        cur.execute("SELECT * FROM bank_table WHERE bank=?", (bank,))
        row = cur.fetchone()
        if row is None:
            print("Bank not found in bank_table")
        else:
            col_headers = [description[0] for description in cur.description]
            for key, val in zip(col_headers, row):
                print(key + ": " + str(val))
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def delete_bank(conn, bank):
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM bank_table WHERE bank=?", (bank,))

        # helper function to traverse the bank table and delete all of its sub banks
        def get_sub_banks(bank):
            select_stmt = "SELECT bank FROM bank_table WHERE parent_bank=?"
            cursor.execute(select_stmt, (bank,))
            rows = cursor.fetchall()

            # we've reached a bank with no sub banks
            if len(rows) == 0:
                select_assoc_stmt = """
                    SELECT username, bank
                    FROM association_table WHERE bank=?
                    """
                for assoc_row in cursor.execute(select_assoc_stmt, (bank,)):
                    u.delete_user(conn, username=assoc_row[0], bank=assoc_row[1])
            # else, delete all of its sub banks and continue traversing
            else:
                for row in rows:
                    cursor.execute("DELETE FROM bank_table WHERE bank=?", (row[0],))
                    get_sub_banks(row[0])

        get_sub_banks(bank)
    # if an exception occcurs while recursively deleting
    # the parent banks, then throw the exception and roll
    # back the changes made to the DB
    except sqlite3.OperationalError as exception:
        print(exception)
        conn.rollback()
        return 1

    # commit changes
    conn.commit()
    return 0


def edit_bank(conn, bank, shares):
    print(shares)
    # if user tries to edit a shares value <= 0,
    # raise an exception
    if int(shares) <= 0:
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
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)
