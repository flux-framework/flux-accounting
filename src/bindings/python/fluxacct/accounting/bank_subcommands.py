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

# helper function to print user information in a table format
def print_user_rows(cur, rows, bank):
    print("\nUsers Under Bank {bank_name}:\n".format(bank_name=bank))
    user_headers = [description[0] for description in cur.description]
    # print column names of association_table
    for header in user_headers:
        print(header.ljust(18), end=" ")
    print()
    for row in rows:
        for col in list(row):
            print(str(col).ljust(18), end=" ")
        print()


# helper function to print bank information in a table format
def print_bank_rows(cur, rows, bank):
    bank_headers = [description[0] for description in cur.description]
    # bank has sub banks, so list them
    for header in bank_headers:
        print(header.ljust(15), end=" ")
    print()
    for row in rows:
        for col in list(row):
            print(str(col).ljust(15), end=" ")
        print()


# helper function to traverse the bank table and delete all sub banks and users
def print_sub_banks(conn, bank, indent=""):
    select_stmt = "SELECT bank FROM bank_table WHERE parent_bank=?"
    cur = conn.cursor()
    cur.execute(select_stmt, (bank,))
    rows = cur.fetchall()

    # we've reached a bank with no sub banks
    if len(rows) == 0:
        cur.execute("SELECT username FROM association_table WHERE bank=?", (bank,))
        rows = cur.fetchall()
        if rows:
            for row in rows:
                print(indent, row[0])
    # else, delete all of its sub banks and continue traversing
    else:
        for row in rows:
            print(indent, row[0])
            print_sub_banks(conn, row[0], indent + " ")


def validate_parent_bank(cur, parent_bank):
    try:
        cur.execute("SELECT shares FROM bank_table WHERE bank=?", (parent_bank,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("Parent bank not found in bank table")
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def add_bank(conn, bank, shares, parent_bank=""):
    cur = conn.cursor()

    # if the parent bank is not "", that means the bank trying
    # to be added wants to be placed under an existing parent bank
    if parent_bank != "":
        validate_parent_bank(cur, parent_bank)

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


def view_bank(conn, bank, tree=False, users=False):
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM bank_table WHERE bank=?", (bank,))
        rows = cur.fetchall()

        if rows:
            print_bank_rows(cur, rows, bank)
        else:
            print("Bank not found in bank_table")
            return

        # print out the hierarchy view with the specified bank as the root of the tree
        if tree is True:
            # get all potential sub banks
            cur.execute("SELECT * FROM bank_table WHERE parent_bank=?", (bank,))
            rows = cur.fetchall()

            if rows:
                print("\n{bank_name}".format(bank_name=bank))
                print_sub_banks(conn, bank, "")
            else:
                print("\nNo sub banks under {bank_name}".format(bank_name=bank))

        # if users is passed in, print out all potential users under passed in bank
        if users is True:
            select_stmt = """
                        SELECT username,userid,default_bank,shares,job_usage,
                        fairshare,max_running_jobs,queues FROM association_table
                        WHERE bank=?
                        """
            cur.execute(
                select_stmt,
                (bank,),
            )
            rows = cur.fetchall()

            if rows:
                print_user_rows(cur, rows, bank)
            else:
                print("\nNo users under {bank_name}".format(bank_name=bank))
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def delete_bank(conn, bank):
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE bank_table SET active=0 WHERE bank=?", (bank,))

        # helper function to traverse the bank table and disable all of its sub banks
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
            # else, disable all of its sub banks and continue traversing
            else:
                for row in rows:
                    cursor.execute(
                        "UPDATE bank_table SET active=0 WHERE bank=?", (row[0],)
                    )
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
