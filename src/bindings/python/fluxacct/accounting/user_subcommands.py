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


def get_uid(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def validate_queue(conn, queue):
    cur = conn.cursor()
    queue_list = queue.split(",")

    for service in queue_list:
        cur.execute("SELECT queue FROM queue_table WHERE queue=?", (service,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("Queue specified does not exist in queue_table")


def view_user(conn, user):
    cur = conn.cursor()
    try:
        # get the information pertaining to a user in the DB
        cur.execute("SELECT * FROM association_table where username=?", (user,))
        rows = cur.fetchall()
        headers = [description[0] for description in cur.description]
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


def add_user(
    conn,
    username,
    bank,
    uid=65534,
    shares=1,
    max_running_jobs=5,
    max_active_jobs=7,
    max_nodes=2147483647,
    queues="",
):

    if uid == 65534:
        # get uid of user
        fetched_uid = get_uid(username)

        try:
            if isinstance(fetched_uid, int):
                uid = fetched_uid
            else:
                raise KeyError
        except KeyError:
            print("could not find UID for user; adding default UID")

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

    # validate the queue specified if any were passed in
    if queues != "":
        try:
            validate_queue(conn, queues)
        except ValueError as err:
            print(err)
            return -1

    try:
        # insert the user values into association_table
        conn.execute(
            """
            INSERT INTO association_table (creation_time, mod_time, username,
                                           userid, bank, default_bank, shares,
                                           max_running_jobs, max_active_jobs,
                                           max_nodes, queues)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                username,
                uid,
                bank,
                default_bank,
                shares,
                max_running_jobs,
                max_active_jobs,
                max_nodes,
                queues,
            ),
        )
        # commit changes
        conn.commit()
        # insert the user values into job_usage_factor_table
        conn.execute(
            """
            INSERT OR IGNORE INTO job_usage_factor_table (username, userid, bank)
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
    max_running_jobs=None,
    max_active_jobs=None,
    max_nodes=None,
    queues=None,
):
    params = locals()
    editable_fields = [
        "username",
        "bank",
        "default_bank",
        "shares",
        "max_running_jobs",
        "max_active_jobs",
        "max_nodes",
        "queues",
    ]
    for field in editable_fields:
        if params[field] is not None:
            if field == "queues":
                try:
                    validate_queue(conn, params[field])
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

    # update mod_time column
    mod_time_tup = (
        int(time.time()),
        username,
    )
    if bank is not None:
        update_stmt = """UPDATE association_table SET mod_time=?
                         WHERE username=? AND bank=?"""
        mod_time_tup = mod_time_tup + (bank,)
    else:
        update_stmt = "UPDATE association_table SET mod_time=? WHERE username=?"

    conn.execute(update_stmt, mod_time_tup)

    # commit changes
    conn.commit()

    return 0
