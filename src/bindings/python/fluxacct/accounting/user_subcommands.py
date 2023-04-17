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

###############################################################
#                                                             #
#                      Helper Functions                       #
#                                                             #
###############################################################
def get_uid(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def set_uid(username, uid):

    if uid == 65534:
        fetched_uid = get_uid(username)

        try:
            if isinstance(fetched_uid, int):
                uid = fetched_uid
            else:
                raise KeyError
        except KeyError:
            uid = 65534

    return uid


def validate_queue(conn, queues):
    cur = conn.cursor()
    queue_list = queues.split(",")

    for queue in queue_list:
        cur.execute("SELECT queue FROM queue_table WHERE queue=?", (queue,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(queue)


def validate_project(conn, projects):
    cur = conn.cursor()
    project_list = projects.split(",")
    project_list.append("*")

    for project in project_list:
        cur.execute("SELECT project FROM project_table WHERE project=?", (project,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(project)

    return ",".join(project_list)


def validate_bank(conn, bank):
    cur = conn.cursor()

    cur.execute("SELECT bank FROM bank_table WHERE bank=?", (bank,))
    row = cur.fetchone()
    if row is None:
        # return the name of the bank that was invalid
        raise ValueError(bank)


def set_default_project(projects):
    if projects != "*":
        project_list = projects.split(",")
        return project_list[0]

    return "*"


def get_user_rows(headers, rows, parseable):
    user_str = ""

    if parseable is True:
        # find length of longest column name
        col_width = len(sorted(headers, key=len)[-1])

        for header in headers:
            user_str += header.ljust(col_width)
        user_str += "\n"
        for row in rows:
            for col in list(row):
                user_str += str(col).ljust(col_width)

        return user_str

    for row in rows:
        # iterate through column names of association_table and
        # print out its associated value
        for key, value in zip(headers, list(row)):
            user_str += key + ": " + str(value) + "\n"
        user_str += "\n"

    return user_str


# check for a default bank of the user being added; if the user is new, set
# the first bank they were added to as their default bank
def set_default_bank(cur, username, bank):
    select_stmt = "SELECT default_bank FROM association_table WHERE username=?"
    cur.execute(select_stmt, (username,))
    row = cur.fetchone()

    if row is None:
        return bank

    return row[0]


# check if association already exists and is active in association_table;
# if so, raise sqlite3.IntegrityError
def association_is_active(cur, username, bank):
    cur.execute(
        "SELECT active FROM association_table WHERE username=? AND bank=?",
        (
            username,
            bank,
        ),
    )
    is_active = cur.fetchall()
    if len(is_active) > 0 and is_active[0][0] == 1:
        return True

    return False


# check if user/bank entry already exists but was disabled first; if so,
# just update the 'active' column in already existing row
def check_if_user_disabled(conn, cur, username, bank):
    cur.execute(
        "SELECT * FROM association_table WHERE username=? AND bank=?",
        (
            username,
            bank,
        ),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        cur.execute(
            "UPDATE association_table SET active=1 WHERE username=? AND bank=?",
            (
                username,
                bank,
            ),
        )
        conn.commit()
        return True

    return False


def get_default_bank(cur, username):
    select_stmt = "SELECT default_bank FROM association_table WHERE username=?"
    cur.execute(select_stmt, (username,))
    rows = cur.fetchall()

    return rows[0][0]


# helper function that is called when a user's default_bank row gets disabled from
# the association_table. It will look for other banks that the user belongs to; if
# so, the default bank needs to be updated for these rows
def update_default_bank(conn, cur, username):
    # get first bank from other potential existing rows from user
    select_stmt = """SELECT bank FROM association_table WHERE active=1 AND username=?
                     ORDER BY creation_time"""
    cur.execute(select_stmt, (username,))
    rows = cur.fetchall()
    # if len(rows) == 0, then the user only belongs to one bank (the bank they are being
    # disabled in); thus the user's default bank does not need to be updated
    if len(rows) > 0:
        # update user rows to have a new default bank (the next earliest user/bank row created)
        new_default_bank = rows[0][0]
        edit_user(conn, username, default_bank=new_default_bank)


def update_mod_time(conn, username, bank):
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


def clear_queues(conn, username, bank=None):
    if bank is None:
        conn.execute(
            "UPDATE association_table SET queues='' WHERE username=?", (username,)
        )
    else:
        conn.execute(
            "UPDATE association_table SET queues='' WHERE username=? AND bank=?",
            (
                username,
                bank,
            ),
        )
        update_mod_time(conn, username, bank)

    conn.commit()

    return 0


###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################
def view_user(conn, user, parseable=False):
    cur = conn.cursor()
    try:
        # get the information pertaining to a user in the DB
        cur.execute("SELECT * FROM association_table where username=?", (user,))
        rows = cur.fetchall()
        headers = [description[0] for description in cur.description]  # column names
        if not rows:
            raise ValueError(f"User {user} not found in association_table")

        user_str = get_user_rows(headers, rows, parseable)

        return user_str
    # this kind of exception is raised for errors related to the DB's operation,
    # not necessarily under the control of the programmer, e.g DB path cannot be
    # found or transaction could not be processed
    # (https://docs.python.org/3/library/sqlite3.html#sqlite3.OperationalError)
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


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
    projects="*",
):
    cur = conn.cursor()

    userid = set_uid(username, uid)

    # if true, association (user, bank) is already active
    # in association_table
    if association_is_active(cur, username, bank):
        raise sqlite3.IntegrityError(
            f"association {username},{bank} already active in association_table"
        )

    # if true, association already exists in table but is not
    # active, so re-activate the association and return
    if check_if_user_disabled(conn, cur, username, bank):
        return 0

    # validate the bank specified if one was passed in
    try:
        validate_bank(conn, bank)
    except ValueError as bad_bank:
        raise ValueError(f"Bank {bad_bank} does not exist in bank_table")

    # set default bank for user
    default_bank = set_default_bank(cur, username, bank)

    # validate the queue(s) specified if any were passed in
    if queues != "":
        try:
            validate_queue(conn, queues)
        except ValueError as bad_queue:
            raise ValueError(f"queue {bad_queue} does not exist in queue_table")

    # validate the project(s) specified if any were passed in;
    # add default project name ('*') to project(s) specified if
    # any were passed in
    if projects != "*":
        try:
            projects = validate_project(conn, projects)
        except ValueError as bad_project:
            raise ValueError(f"project {bad_project} does not exist in project_table")

    # determine default_project for user; if no other projects
    # were specified, use '*' as the default. If a project was
    # specified, then use the first one as the default
    default_project = set_default_project(projects)

    try:
        # insert the user values into association_table
        conn.execute(
            """
            INSERT INTO association_table (creation_time, mod_time, username,
                                           userid, bank, default_bank, shares,
                                           max_running_jobs, max_active_jobs,
                                           max_nodes, queues, projects, default_project)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                username,
                userid,
                bank,
                default_bank,
                shares,
                max_running_jobs,
                max_active_jobs,
                max_nodes,
                queues,
                projects,
                default_project,
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

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError:
        raise sqlite3.IntegrityError()


def delete_user(conn, username, bank):
    cur = conn.cursor()

    # set deleted flag in user row
    update_stmt = "UPDATE association_table SET active=0 WHERE username=? AND bank=?"
    conn.execute(
        update_stmt,
        (
            username,
            bank,
        ),
    )
    # commit changes
    conn.commit()

    # check if bank being deleted is the user's default bank
    default_bank = get_default_bank(cur, username)

    # if the user belongs to multiple banks and the bank being disabled
    # is the user's default bank, then we need to update the default
    # bank for the other rows
    if default_bank == bank:
        update_default_bank(conn, cur, username)

    return 0


def edit_user(
    conn,
    username,
    bank=None,
    userid=None,
    default_bank=None,
    shares=None,
    max_running_jobs=None,
    max_active_jobs=None,
    max_nodes=None,
    queues=None,
    projects=None,
    default_project=None,
):
    params = locals()
    editable_fields = [
        "username",
        "bank",
        "userid",
        "default_bank",
        "shares",
        "max_running_jobs",
        "max_active_jobs",
        "max_nodes",
        "queues",
        "projects",
        "default_project",
    ]
    for field in editable_fields:
        if params[field] is not None:
            if field == "queues":
                # if --queues is empty, clear the available
                # queues to the user
                if params[field] == "":
                    clear_queues(conn, username, bank=None)
                    return 0
                try:
                    validate_queue(conn, params[field])
                except ValueError as bad_queue:
                    raise ValueError(f"queue {bad_queue} does not exist in queue_table")
            if field == "projects":
                try:
                    params[field] = validate_project(conn, params[field])
                except ValueError as bad_project:
                    raise ValueError(
                        f"project {bad_project} does not exist in project_table"
                    )

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
    update_mod_time(conn, username, bank)

    # commit changes
    conn.commit()

    return 0
