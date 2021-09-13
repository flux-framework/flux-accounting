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
import pwd


def view_user(conn, user):
    cur = conn.cursor()
    try:
        # get the information pertaining to a user in the DB
        cur.execute("SELECT * FROM association_table where username=?", (user,))
        row = cur.fetchone()
        if row is None:
            print("User not found in association_table")
        else:
            col_headers = [description[0] for description in cur.description]
            for key, val in zip(col_headers, row):
                print(key + ": " + str(val))
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def get_uid(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def add_user(
    conn,
    username,
    bank,
    uid=65534,
    admin_level=1,
    shares=1,
    max_jobs=5,
    qos="",
):

    # get uid of user
    fetched_uid = get_uid(username)

    try:
        if isinstance(fetched_uid, int):
            uid = fetched_uid
        else:
            raise KeyError
    except KeyError as key_error:
        print(key_error)

    # check for a default bank of the user being added; if the user is new, set
    # the first bank they were added to as their default bank
    cur = conn.cursor()
    select_stmt = "SELECT default_bank FROM association_table WHERE username=?"
    cur.execute(select_stmt, (username,))
    row = cur.fetchone()

    if row is None:
        default_bank = bank
    else:
        default_bank = row[0]

    try:
        # insert the user values into association_table
        conn.execute(
            """
            INSERT INTO association_table (
                creation_time,
                mod_time,
                deleted,
                username,
                userid,
                admin_level,
                bank,
                default_bank,
                shares,
                max_jobs,
                qos
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                0,
                username,
                uid,
                admin_level,
                bank,
                default_bank,
                shares,
                max_jobs,
                qos,
            ),
        )
        # commit changes
        conn.commit()
        # insert the user values into job_usage_factor_table
        conn.execute(
            """
            INSERT INTO job_usage_factor_table (
                username,
                userid,
                bank
            )
            VALUES (?, ?, ?)
            """,
            (
                username,
                uid,
                bank,
            ),
        )
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def delete_user(conn, username, bank):
    # delete user account from association_table
    delete_stmt = "DELETE FROM association_table WHERE username=? AND bank=?"
    cursor = conn.cursor()
    cursor.execute(
        delete_stmt,
        (
            username,
            bank,
        ),
    )
    # commit changes
    conn.commit()


def edit_user(conn, username, field, new_value, bank=""):
    fields = [
        "username",
        "admin_level",
        "bank",
        "default_bank",
        "shares",
        "max_jobs",
    ]
    if field in fields:
        the_field = field

        if bank != "":
            update_stmt = (
                "UPDATE association_table SET "
                + the_field
                + "=? WHERE username=? AND bank=?"
            )
            # edit value in accounting database
            conn.execute(
                update_stmt,
                (
                    new_value,
                    username,
                    bank,
                ),
            )
        else:
            update_stmt = (
                "UPDATE association_table SET " + the_field + "=? WHERE username=?"
            )
            conn.execute(
                update_stmt,
                (
                    new_value,
                    username,
                ),
            )

        # commit changes
        conn.commit()
    else:
        raise ValueError("Field not found in association table")
