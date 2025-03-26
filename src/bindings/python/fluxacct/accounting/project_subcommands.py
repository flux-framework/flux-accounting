#!/usr/bin/env python3

###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sqlite3

import fluxacct.accounting
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql

###############################################################
#                                                             #
#                      Helper Functions                       #
#                                                             #
###############################################################


def project_is_active(cur, project):
    """
    Check if the project already exists and is active in the projects table.
    """
    cur.execute(
        "SELECT * FROM project_table WHERE project=?",
        (project,),
    )
    project_exists = cur.fetchall()
    if len(project_exists) > 0:
        return True

    return False


###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################


def view_project(conn, project, parsable=False):
    try:
        cur = conn.cursor()
        # get the information pertaining to a project in the DB
        cur.execute("SELECT * FROM project_table where project=?", (project,))

        formatter = fmt.ProjectFormatter(cur, project)

        if parsable:
            return formatter.as_table()
        return formatter.as_json()
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


def add_project(conn, project):
    cur = conn.cursor()

    if project_is_active(cur, project):
        raise sqlite3.IntegrityError(
            f"project {project} already exists in project_table"
        )

    try:
        insert_stmt = "INSERT INTO project_table (project) VALUES (?)"
        conn.execute(
            insert_stmt,
            (project,),
        )

        conn.commit()

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError:
        raise sqlite3.IntegrityError(
            f"project {project} already exists in project_table"
        )


def delete_project(conn, project):
    cursor = conn.cursor()

    # look for any rows in the association_table that reference this project
    select_stmt = "SELECT * FROM association_table WHERE projects LIKE ?"
    cursor.execute(select_stmt, ("%" + project + "%",))
    result = cursor.fetchall()
    warning_stmt = (
        "WARNING: user(s) in the association_table still "
        "reference this project. Make sure to edit user rows to "
        "account for this deleted project."
    )

    delete_stmt = "DELETE FROM project_table WHERE project=?"
    cursor.execute(delete_stmt, (project,))

    conn.commit()

    # if len(rows) > 0, this means that at least one association in the
    # association_table references this project. If this is the case,
    # return the warning message after deleting the project.
    if len(result) > 0:
        return warning_stmt

    return 0


def list_projects(conn, cols=None, table=False):
    """
    List all of the available projects registered in the project_table.

    Args:
        cols: a list of columns from the table to include in the output. By default, all
            columns are included.
        table: output data in bank_table in table format. By default, the format of any
            returned data is in JSON.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.PROJECT_TABLE

    try:
        cur = conn.cursor()

        sql.validate_columns(cols, fluxacct.accounting.PROJECT_TABLE)
        # construct SELECT statement
        select_stmt = f"SELECT {', '.join(cols)} FROM project_table"
        cur.execute(select_stmt)

        # initialize AccountingFormatter object
        formatter = fmt.AccountingFormatter(cur)
        if table:
            return formatter.as_table()
        return formatter.as_json()
    except sqlite3.Error as err:
        raise sqlite3.Error(f"list-projects: an sqlite3.Error occurred: {err}")
    except ValueError as exc:
        raise ValueError(f"list-projects: {exc}")
