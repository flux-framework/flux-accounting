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


def view_project(conn, project):
    cur = conn.cursor()
    try:
        # get the information pertaining to a project in the DB
        cur.execute("SELECT * FROM project_table where project=?", (project,))
        rows = cur.fetchall()
        headers = [description[0] for description in cur.description]
        project_str = ""
        if not rows:
            raise ValueError(f"Project {project} not found in project_table")

        for header in headers:
            project_str += header.ljust(18)
        project_str += "\n"
        for row in rows:
            for col in list(row):
                project_str += str(col).ljust(18)
            project_str += "\n"

        return project_str
    except sqlite3.OperationalError as e_database_error:
        return e_database_error


def add_project(conn, project):
    try:
        insert_stmt = "INSERT INTO project_table (project) VALUES (?)"
        conn.execute(
            insert_stmt,
            (project,),
        )

        conn.commit()

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        return integrity_error


def delete_project(conn, project):
    cursor = conn.cursor()

    # look for any rows in the association_table that reference this project
    select_stmt = "SELECT * FROM association_table WHERE projects LIKE ?"
    cursor.execute(select_stmt, ("%" + project + "%",))
    rows = cursor.fetchall()
    warning_stmt = (
        "WARNING: user(s) in the assocation_table still "
        "reference this project. Make sure to edit user rows to "
        "account for this deleted project."
    )

    delete_stmt = "DELETE FROM project_table WHERE project=?"
    cursor.execute(delete_stmt, (project,))

    conn.commit()

    # if len(rows) > 0, this means that at least one association in the
    # association_table references this project. If this is the case,
    # return the warning message after deleting the project.
    if len(rows) > 0:
        return warning_stmt

    return 0
