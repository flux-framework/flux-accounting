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
    headers = [
        "creation_time",
        "mod_time",
        "deleted",
        "username",
        "userid",
        "admin_level",
        "bank",
        "default_bank",
        "shares",
        "job_usage",
        "fairshare",
        "max_jobs",
        "qos",
    ]
    try:
        # get the information pertaining to a user in the DB
        cur.execute("SELECT * FROM association_table where username=?", (user,))
        rows = cur.fetchall()
        if not rows:
            print("User not found in association_table")
        else:
            # print column names of association_table
            for header in headers:
                print(header.ljust(15), end=" ")
            print()
            for row in rows:
                for col in list(row):
                    print(str(col).ljust(15), end=" ")
                print()
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def get_uid(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def validate_qos(conn, qos):
    cur = conn.cursor()
    qos_list = qos.split(",")

    for service in qos_list:
        cur.execute("SELECT qos FROM qos_table WHERE qos=?", (service,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("QOS specified does not exist in qos_table")


def add_user(
    conn,
    username,
    bank,
    uid=65534,
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

    # validate the qos specified if any were passed in
    if qos != "":
        try:
            validate_qos(conn, qos)
        except ValueError as err:
            print(err)
            return -1

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
                bank,
                default_bank,
                shares,
                max_jobs,
                qos
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                0,
                username,
                uid,
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
        return -1

    return 0


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


def edit_user(
    conn,
    username,
    bank=None,
    default_bank=None,
    shares=None,
    max_jobs=None,
    qos=None,
):
    params = locals()
    editable_fields = [
        "username",
        "bank",
        "default_bank",
        "shares",
        "max_jobs",
        "qos",
    ]
    for field in editable_fields:
        if params[field] is not None:
            if field == "qos":
                try:
                    validate_qos(conn, params[field])
                except ValueError as err:
                    print(err)
                    return -1

            update_stmt = "UPDATE association_table SET " + field

            # passing -1 will reset the column to its default value
            if params[field] == "-1":
                update_stmt += "=NULL WHERE username=?"
                tup = (username,)
            else:
                update_stmt += "=? WHERE username=?"
                tup = (
                    params[field],
                    username,
                )

            if bank is not None:
                update_stmt += " AND BANK=?"
                tup = tup + (bank,)

            conn.execute(update_stmt, tup)

            # commit changes
            conn.commit()

    return 0
