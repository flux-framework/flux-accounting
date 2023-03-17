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

###############################################################
#                                                             #
#                      Helper Functions                       #
#                                                             #
###############################################################

# helper function to print user information in a table format
def print_user_rows(cur, rows, bank):
    user_str = "\nUsers Under Bank {bank_name}:\n\n".format(bank_name=bank)
    user_headers = [description[0] for description in cur.description]
    # print column names of association_table
    for header in user_headers:
        user_str += header.ljust(18)
    user_str += "\n"
    for row in rows:
        for col in list(row):
            user_str += str(col).ljust(18)
        user_str += "\n"

    return user_str


# helper function to print bank information in a table format
def get_bank_rows(cur, rows, bank):
    bank_str = ""
    bank_headers = [description[0] for description in cur.description]
    # bank has sub banks, so list them
    for header in bank_headers:
        bank_str += header.ljust(15)
    bank_str += "\n"
    for row in rows:
        for col in list(row):
            bank_str += str(col).ljust(15)
        bank_str += "\n"

    return bank_str


# helper function to traverse the bank table and delete all sub banks and users
def print_sub_banks(conn, bank, bank_str, indent=""):
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
                bank_str += indent + " " + row[0] + "\n"
    # else, delete all of its sub banks and continue traversing
    else:
        for row in rows:
            bank_str += indent + " " + row[0] + "\n"
            bank_str = print_sub_banks(conn, row[0], bank_str, indent + " ")

    return bank_str


def validate_parent_bank(cur, parent_bank):
    try:
        cur.execute("SELECT shares FROM bank_table WHERE bank=?", (parent_bank,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(parent_bank)

        return 0
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


# check if bank already exists and is active in bank_table;
# if so, return True
def bank_is_active(cur, bank, parent_bank):
    cur.execute(
        "SELECT active FROM bank_table WHERE bank=? AND parent_bank=?",
        (
            bank,
            parent_bank,
        ),
    )
    is_active = cur.fetchall()
    if len(is_active) > 0 and is_active[0][0] == 1:
        return True

    return False


# check if bank already exists but was disabled first; if so,
# just update the 'active' column in already existing row
def check_if_bank_disabled(cur, bank, parent_bank):
    cur.execute(
        "SELECT * FROM bank_table WHERE bank=? AND parent_bank=?",
        (bank, parent_bank),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return True

    return False


# re-enable bank in bank_table by setting "active" to 1
def reactivate_bank(conn, cur, bank, parent_bank):
    cur.execute(
        "UPDATE bank_table SET active=1 WHERE bank=? AND parent_bank=?",
        (
            bank,
            parent_bank,
        ),
    )
    conn.commit()


###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################


def add_bank(conn, bank, shares, parent_bank=""):
    cur = conn.cursor()

    # if the parent bank is not "", that means the bank trying
    # to be added wants to be placed under an existing parent bank
    try:
        if parent_bank != "":
            validate_parent_bank(cur, parent_bank)
    except ValueError as bad_parent_bank:
        raise ValueError(f"parent bank {bad_parent_bank} not found in bank table")
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(exc)

    # check if bank already exists and is active in bank_table; if so, raise
    # a sqlite3.IntegrityError
    if bank_is_active(cur, bank, parent_bank):
        raise sqlite3.IntegrityError(f"bank {bank} already exists in bank_table")

    # if true, bank already exists in table but is not
    # active, so re-activate the bank and return
    if check_if_bank_disabled(cur, bank, parent_bank):
        reactivate_bank(conn, cur, bank, parent_bank)
        return 0

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

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError:
        raise sqlite3.IntegrityError(f"bank {bank} already exists in bank_table")


def view_bank(conn, bank, tree=False, users=False):
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM bank_table WHERE bank=?", (bank,))
        rows = cur.fetchall()

        if rows:
            bank_str = get_bank_rows(cur, rows, bank)
        else:
            raise ValueError(f"bank {bank} not found in bank_table")

        # print out the hierarchy view with the specified bank as the root of the tree
        if tree is True:
            # get all potential sub banks
            cur.execute("SELECT * FROM bank_table WHERE parent_bank=?", (bank,))
            rows = cur.fetchall()

            if rows:
                bank_hierarchy_str = bank + "\n"
                bank_hierarchy_str = print_sub_banks(conn, bank, bank_hierarchy_str, "")
                bank_str += "\n" + bank_hierarchy_str
            else:
                bank_str += "no sub banks under " + bank
        # if users is passed in, print out all potential users under
        # the passed in bank
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
                user_str = print_user_rows(cur, rows, bank)
                bank_str += user_str
            else:
                bank_str += "\nno users under {bank_name}".format(bank_name=bank)

        return bank_str
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


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
    except sqlite3.OperationalError as exc:
        conn.rollback()
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")

    # commit changes
    conn.commit()
    return 0


def edit_bank(
    conn,
    bank=None,
    shares=None,
    parent_bank=None,
):
    cur = conn.cursor()
    params = locals()
    editable_fields = [
        "shares",
        "parent_bank",
    ]
    for field in editable_fields:
        if params[field] is not None:
            if field == "parent_bank":
                try:
                    validate_parent_bank(cur, params[field])
                except ValueError as bad_parent_bank:
                    raise ValueError(
                        f"parent bank {bad_parent_bank} not found in bank table"
                    )
                except sqlite3.OperationalError as exc:
                    raise sqlite3.OperationalError(exc)
            if field == "shares":
                if int(shares) <= 0:
                    raise ValueError("new shares amount must be >= 0")

            update_stmt = "UPDATE bank_table SET " + field

            update_stmt += "=? WHERE bank=?"
            tup = (
                params[field],
                bank,
            )
            conn.execute(update_stmt, tup)

    # commit changes
    conn.commit()

    return 0
