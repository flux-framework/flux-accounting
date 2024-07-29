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


def print_user_rows(cur, rows, bank):
    """Print user information in a table format."""
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


def get_bank_rows(cur, rows, bank):
    """Print bank information in a table format."""
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


def print_sub_banks(conn, bank, bank_str, indent=""):
    """Traverse the bank table and print all sub banks ansd users."""
    select_stmt = "SELECT bank FROM bank_table WHERE parent_bank=?"
    cur = conn.cursor()
    cur.execute(select_stmt, (bank,))
    result = cur.fetchall()

    # we've reached a bank with no sub banks
    if len(result) == 0:
        cur.execute("SELECT username FROM association_table WHERE bank=?", (bank,))
        result = cur.fetchall()
        if result:
            for row in result:
                bank_str += indent + " " + row[0] + "\n"
    # else, delete all of its sub banks and continue traversing
    else:
        for row in result:
            bank_str += indent + " " + row[0] + "\n"
            bank_str = print_sub_banks(conn, row[0], bank_str, indent + " ")

    return bank_str


def validate_parent_bank(cur, parent_bank):
    try:
        cur.execute("SELECT shares FROM bank_table WHERE bank=?", (parent_bank,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(parent_bank)

        return 0
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


def bank_is_active(cur, bank, parent_bank):
    """Check if the bank already exists and is active."""
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


def check_if_bank_disabled(cur, bank, parent_bank):
    """
    Check if the bank already exists but was disabled first. If so, just
    update the 'active' column in the alread existing row.
    """
    cur.execute(
        "SELECT * FROM bank_table WHERE bank=? AND parent_bank=?",
        (bank, parent_bank),
    )
    result = cur.fetchall()
    if len(result) == 1:
        return True

    return False


def reactivate_bank(conn, cur, bank, parent_bank):
    """Re-enable the bank by setting 'active' to 1."""
    cur.execute(
        "UPDATE bank_table SET active=1 WHERE bank=? AND parent_bank=?",
        (
            bank,
            parent_bank,
        ),
    )
    conn.commit()


def print_hierarchy(cur, bank, hierarchy_str, indent=""):
    # look for all sub banks under this parent bank
    select_stmt = "SELECT bank,shares,job_usage FROM bank_table WHERE parent_bank=?"
    cur.execute(select_stmt, (bank,))
    sub_banks = cur.fetchall()

    if len(sub_banks) == 0:
        # we've reached a bank with no sub banks, so print out every user
        # under this bank
        cur.execute(
            "SELECT username,shares,job_usage,fairshare FROM association_table WHERE bank=?",
            (bank,),
        )
        users = cur.fetchall()
        if users:
            for user in users:
                hierarchy_str += (
                    indent
                    + " "
                    + bank.ljust(20)
                    + str(user[0]).rjust(20 - (len(indent) + 1))
                    + str(user[1]).rjust(20)
                    + str(user[2]).rjust(20)
                    + str(user[3]).rjust(20)
                    + "\n"
                )
    else:
        # continue traversing the hierarchy
        for sub_bank in sub_banks:
            hierarchy_str += (
                indent
                + " "
                + str(sub_bank[0]).ljust(20)
                + "".rjust(20 - (len(indent) + 1))  # this skips the "Username" column
                + str(sub_bank[1]).rjust(20)
                + str(sub_bank[2]).rjust(20)
                + "\n"
            )
            hierarchy_str = print_hierarchy(
                cur, sub_bank[0], hierarchy_str, indent + " "
            )

    return hierarchy_str


def print_parsable_hierarchy(cur, bank, hierarchy_str, indent=""):
    # look for all sub banks under this parent bank
    select_stmt = "SELECT bank,shares,job_usage FROM bank_table WHERE parent_bank=?"
    cur.execute(select_stmt, (bank,))
    sub_banks = cur.fetchall()

    if len(sub_banks) == 0:
        # we've reached a bank with no sub banks, so print out every user
        # under this bank
        cur.execute(
            "SELECT username,shares,job_usage,fairshare FROM association_table WHERE bank=?",
            (bank,),
        )
        users = cur.fetchall()
        if users:
            for user in users:
                hierarchy_str += (
                    f"{indent} {bank}|{user[0]}|{user[1]}|{user[2]}|{user[3]}\n"
                )
    else:
        # continue traversing the hierarchy
        for sub_bank in sub_banks:
            hierarchy_str += (
                f"{indent} {str(sub_bank[0])}||{str(sub_bank[1])}|{str(sub_bank[2])}\n"
            )
            hierarchy_str = print_parsable_hierarchy(
                cur, sub_bank[0], hierarchy_str, indent + " "
            )

    return hierarchy_str


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


def view_bank(conn, bank, tree=False, users=False, parsable=False):
    cur = conn.cursor()
    bank_str = ""
    try:
        cur.execute("SELECT * FROM bank_table WHERE bank=?", (bank,))
        result = cur.fetchall()

        if result:
            bank_str = get_bank_rows(cur, result, bank)
        else:
            raise ValueError(f"bank {bank} not found in bank_table")

        name = result[0][1]
        shares = result[0][4]
        usage = result[0][5]

        if parsable is True:
            # print out the database hierarchy starting with the bank passed in
            hierarchy_str = "Bank|Username|RawShares|RawUsage|Fairshare\n"
            hierarchy_str += f"{name}||{str(shares)}|{str(round(usage, 2))}\n"
            hierarchy_str = print_parsable_hierarchy(cur, bank, hierarchy_str, "")
            return hierarchy_str
        if tree is True:
            # print out the hierarchy view with the specified bank as the root of the tree
            hierarchy_str = (
                "Bank".ljust(20)
                + "Username".rjust(20)
                + "RawShares".rjust(20)
                + "RawUsage".rjust(20)
                + "Fairshare".rjust(20)
                + "\n"
            )
            # add the bank passed in to the hierarchy string
            hierarchy_str += (
                name.ljust(20)
                + "".rjust(20)
                + str(shares).rjust(20)
                + str(round(usage, 2)).rjust(20)
                + "\n"
            )

            hierarchy_str = print_hierarchy(cur, name, hierarchy_str, "")
            bank_str += "\n" + hierarchy_str
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
            result = cur.fetchall()

            if result:
                user_str = print_user_rows(cur, result, bank)
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
            result = cursor.fetchall()

            # we've reached a bank with no sub banks
            if len(result) == 0:
                select_assoc_stmt = """
                    SELECT username, bank
                    FROM association_table WHERE bank=?
                    """
                for assoc_row in cursor.execute(select_assoc_stmt, (bank,)):
                    u.delete_user(conn, username=assoc_row[0], bank=assoc_row[1])
            # else, disable all of its sub banks and continue traversing
            else:
                for row in result:
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
