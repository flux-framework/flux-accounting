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

    if result:
        return result[0][0]
    return None


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
def view_user(
    conn, user, parsable=False, cols=None, list_banks=False, format_string=""
):
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

        if format_string != "":
            return formatter.as_format_string(format_string)
        if list_banks:
            return formatter.list_banks()
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


def list_users(conn, cols=None, json_fmt=False, format_string="", **kwargs):
    """
    List all associations in the association_table in the flux-accounting DB. If
    filters are passed in, limit the associations returned to the ones which fit
    all filters.

    Args:
        conn: a SQLite connection object
        cols: a list of columns from the table to include in the output. By default, all
            columns are included.
        format_string: a format string defining how each row should be formatted. Column
            names should be used as placeholders.
        **kwargs: a list of optional constraints to filter the association_table by.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.ASSOCIATION_TABLE

    # if any filters are passed in, make sure they are valid columns
    table_filters = {key: val for key, val in kwargs.items() if val is not None}

    try:
        cur = conn.cursor()

        sql.validate_columns(cols, fluxacct.accounting.ASSOCIATION_TABLE)
        # construct SELECT statement
        select_stmt = f"SELECT {', '.join(cols)} FROM association_table"
        # filter by any constraints passed in
        where_clauses = []
        filters_list = []
        for table_filter in table_filters:
            if table_filter in ("queues", "projects", "default_project"):
                # we are filtering the table with a string; append wildcards ('%') to
                # the string so we can match multiple cases (e.g the association belongs
                # to more than one queue or project)
                where_clauses.append(f"{table_filter} LIKE ?")
                filters_list.append(f"%{table_filters[table_filter]}%")
            else:
                where_clauses.append(f"{table_filter} = ?")
                filters_list.append(table_filters[f"{table_filter}"])

        if where_clauses:
            select_stmt += " WHERE " + " AND ".join(where_clauses)

        cur.execute(select_stmt, tuple(filters_list))

        # initialize AccountingFormatter object
        formatter = fmt.AccountingFormatter(cur)
        if format_string != "":
            return formatter.as_format_string(format_string)
        if json_fmt:
            return formatter.as_json()
        return formatter.as_table()
    except sqlite3.Error as err:
        raise sqlite3.Error(f"list-users: an sqlite3.Error occurred: {err}")
    except ValueError as exc:
        raise ValueError(f"list-users: {exc}")


def add_user(
    conn,
    username,
    bank,
    uid=65534,
    shares=1,
    fairshare=0.5,
    max_running_jobs=5,
    max_active_jobs=7,
    max_nodes=2147483647,
    max_cores=2147483647,
    queues="",
    projects="*",
    default_project=None,
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

    # Determine the default project for user. If no projects were specified, use '*' as
    # the default. If projects were specified and a default project name was not passed,
    # use the first project specified as the default.
    if not default_project:
        default_project = set_default_project(projects)
    else:
        # a default project was specified; make sure it is also a part of the projects
        # list, and if not, add it
        if default_project not in projects.split(","):
            projects += f",{default_project}"

    try:
        # insert the user values into association_table
        conn.execute(
            """
            INSERT INTO association_table (creation_time, mod_time, username,
                                           userid, bank, default_bank, shares,
                                           fairshare, max_running_jobs, max_active_jobs,
                                           max_nodes, max_cores, queues, projects,
                                           default_project)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                username,
                userid,
                bank,
                default_bank,
                shares,
                fairshare,
                max_running_jobs,
                max_active_jobs,
                max_nodes,
                max_cores,
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


def delete_user(conn, username, bank, force=False):
    """
    Deactivate a user row in the association_table by setting its 'active' status to 0.
    If force=True, actually remove the user row from the association_table. If the
    association belongs to multiple banks and the row being deactivated or removed is
    the user's default bank, update other rows to set the new default bank to one that
    is currently active.

    Args:
        conn: The SQLite Connection object
        username: the name of the user
        bank: the bank that the user belongs to
        force: an option to actually remove the row from the association_table instead of
            just setting the 'active' column to 0.
    """
    cur = conn.cursor()
    sql_stmt = "UPDATE association_table SET active=0 WHERE username=? AND bank=?"

    if force:
        sql_stmt = "DELETE FROM association_table WHERE username=? AND bank=?"

    conn.execute(
        sql_stmt,
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
        fairshare: The ratio between the amount of resources an association is
            allocated versus the amount actually consumed.
        max_running_jobs: The max number of running jobs the association can have at any
            given time.
        max_active_jobs: The max number of both pending and running jobs the association
            can have at any given time.
        max_nodes: The man number of nodes an association can have across all of their
            running jobs.
        max_cores: The max number of cores an association can have across all of their
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
        "fairshare",
        "max_running_jobs",
        "max_active_jobs",
        "max_nodes",
        "max_cores",
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
