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

import fluxacct.accounting
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql

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
        result = cur.fetchone()
        if result is None:
            raise ValueError(queue)


def validate_project(conn, projects):
    cur = conn.cursor()
    project_list = projects.split(",")
    project_list.append("*")

    for project in project_list:
        cur.execute("SELECT project FROM project_table WHERE project=?", (project,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(project)

    return ",".join(project_list)


def validate_bank(conn, bank):
    cur = conn.cursor()

    cur.execute("SELECT bank FROM bank_table WHERE bank=?", (bank,))
    result = cur.fetchone()
    if result is None:
        # return the name of the bank that was invalid
        raise ValueError(bank)


def set_default_project(projects):
    if projects != "*":
        project_list = projects.split(",")
        return project_list[0]

    return "*"


def set_default_bank(cur, username, bank):
    """
    Check the default bank of the user being added; if the user is new, set
    the first bank they were added to as their default bank.
    """
    select_stmt = "SELECT default_bank FROM association_table WHERE username=?"
    cur.execute(select_stmt, (username,))
    result = cur.fetchone()

    if result is None:
        return bank

    return result[0]


def association_is_active(cur, username, bank):
    """Check if association already exists and is active."""
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


def check_if_user_disabled(conn, cur, username, bank):
    """
    Check if the association already exists but was disabled; if so, just
    update the 'active' column in the already-existing row.
    """
    cur.execute(
        "SELECT * FROM association_table WHERE username=? AND bank=?",
        (
            username,
            bank,
        ),
    )
    result = cur.fetchall()
    if len(result) == 1:
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
    result = cur.fetchall()

    return result[0][0]


def update_default_bank(conn, cur, username):
    """
    Look for other banks that a user belongs to in the event when a user's
    default bank is disabled. It will look for other banks that the user
    belongs to; if so, the default bank needs to be updated for these rows.
    """
    # get first bank from other potential existing rows from user
    select_stmt = """SELECT bank FROM association_table WHERE active=1 AND username=?
                     ORDER BY creation_time"""
    cur.execute(select_stmt, (username,))
    result = cur.fetchall()
    # if len(result) == 0, then the user only belongs to one bank (the bank they are being
    # disabled in); thus the user's default bank does not need to be updated
    if len(result) > 0:
        # update user rows to have a new default bank (the next earliest user/bank created)
        new_default_bank = result[0][0]
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


def clear_projects(conn, username, bank=None):
    update_stmt = "UPDATE association_table SET projects='*' WHERE username=?"
    if bank is None:
        conn.execute(update_stmt, (username,))
    else:
        update_stmt += " AND bank=?"
        conn.execute(
            update_stmt,
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
def view_user(conn, user, parsable=False, cols=None):
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.ASSOCIATION_TABLE

    try:
        cur = conn.cursor()

        sql.validate_columns(cols, fluxacct.accounting.ASSOCIATION_TABLE)
        # construct SELECT statement
        select_stmt = (
            f"SELECT {', '.join(cols)} FROM association_table WHERE username=?"
        )
        cur.execute(select_stmt, (user,))

        # initialize AssociationFormatter object
        formatter = fmt.AssociationFormatter(cur, user)

        if parsable:
            return formatter.as_table()
        return formatter.as_json()
    # this kind of exception is raised for errors related to the DB's operation,
    # not necessarily under the control of the programmer, e.g DB path cannot be
    # found or transaction could not be processed
    # (https://docs.python.org/3/library/sqlite3.html#sqlite3.OperationalError)
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(
            f"view-user: an sqlite3.OperationalError occurred: {exc}"
        )
    except ValueError as exc:
        raise ValueError(f"view-user: {exc}")


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


def edit_user(conn, username, bank=None, **kwargs):
    """
    Edit a field for an association in the association_table. If "bank" is not passed,
    edit the column across every row for the user in the association_table. If -1 is
    passed for any of the fields, reset the field to its default value in the
    association_table.

    Args:
        username: The username of the association.
        userid: The user ID for the user.
        default_bank: The user's default bank.
        shares: The amount of available resources their organization considers the user
            should be entitled to use relative to other competing users.
        max_running_jobs: The max number of running jobs the association can have at any
            given time.
        max_active_jobs: The max number of both pending and running jobs the association
            can have at any given time.
        max_nodes: The man number of nodes an association can have across all of their
            running jobs.
        queues: A comma-separated list of all of the queues an association can run jobs
            under.
        projects: A comma-separated list of all of the projects an association can run jobs
            under.
        default_project: The association's default project.

    Raises:
        ValueError: if:
            * no fields are provided for the association's update.
            * the default bank for an association is attempted to be reset with -1
            * a queue being passed-in cannot be found in queue_table.
            * a project being passed-in cannot be found in project_table.
    """
    editable_fields = {
        "userid",
        "default_bank",
        "shares",
        "max_running_jobs",
        "max_active_jobs",
        "max_nodes",
        "queues",
        "projects",
        "default_project",
    }
    updates = {
        field: value for field, value in kwargs.items() if field in editable_fields
    }

    if not updates:
        # no editable fields were provided; raise an exception
        raise ValueError("no fields provided for update")

    for field, value in updates.items():
        if value is not None:
            if str(value) == "-1":
                if field == "default_bank":
                    raise ValueError(
                        f"default bank cannot be reset with -1; please specify a value"
                    )
                # clear either the queues or the projects
                if field == "queues":
                    clear_queues(conn, username, bank)
                elif field == "projects":
                    clear_projects(conn, username, bank)
                else:
                    # for the other fields, setting to NULL will reset it to its default value
                    update_stmt = (
                        f"UPDATE association_table SET {field}=NULL WHERE username=?"
                    )
                    tup = (username,)

                    if bank is not None:
                        update_stmt += " AND bank=?"
                        tup = tup + (bank,)

                    conn.execute(update_stmt, tup)

                # skip the rest of the loop if reset logic was handled
                continue

            if field == "queues":
                try:
                    validate_queue(conn, value)
                except ValueError as bad_queue:
                    raise ValueError(f"queue {bad_queue} does not exist in queue_table")
            elif field == "projects":
                try:
                    updates[field] = validate_project(conn, value)
                except ValueError as bad_project:
                    raise ValueError(
                        f"project {bad_project} does not exist in project_table"
                    )

            update_stmt = f"UPDATE association_table SET {field}=? WHERE username=?"
            tup = (updates[field], username)

            if bank is not None:
                update_stmt += " AND bank=?"
                tup = tup + (bank,)

            conn.execute(update_stmt, tup)

    # update mod_time column
    update_mod_time(conn, username, bank)

    # commit changes
    conn.commit()

    return 0
