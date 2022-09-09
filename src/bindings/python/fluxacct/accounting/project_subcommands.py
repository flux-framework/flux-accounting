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
        if not rows:
            print("Project not found in project_table")
        else:
            # print column names of project_table
            for header in headers:
                print(header.ljust(18), end=" ")
            print()
            for row in rows:
                for col in list(row):
                    print(str(col).ljust(18), end=" ")
                print()
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def add_project(conn, project):
    try:
        insert_stmt = "INSERT INTO project_table (project) VALUES (?)"
        conn.execute(
            insert_stmt,
            (project,),
        )

        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def delete_project(conn, project):
    cursor = conn.cursor()

    # look for any rows in the association_table that reference this project
    select_stmt = "SELECT * FROM association_table WHERE projects LIKE ?"
    cursor.execute(select_stmt, ("%" + project + "%",))
    rows = cursor.fetchall()
    if len(rows) > 0:
        print(
            """WARNING: user(s) in the assocation_table still reference this project.
                 Make sure to edit user rows to account for this deleted project."""
        )

    delete_stmt = "DELETE FROM project_table WHERE project=?"
    cursor.execute(delete_stmt, (project,))

    conn.commit()
