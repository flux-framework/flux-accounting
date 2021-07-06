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

import pandas as pd


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
                shares
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                0,
                username,
                uid,
                admin_level,
                bank,
                shares,
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


def edit_user(conn, username, field, new_value):
    fields = [
        "username",
        "admin_level",
        "bank",
        "shares",
        "max_jobs",
        "max_wall_pj",
    ]
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
