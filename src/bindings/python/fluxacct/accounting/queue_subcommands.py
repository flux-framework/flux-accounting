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


def view_queue(conn, queue):
    cur = conn.cursor()
    try:
        # get the information pertaining to a queue in the DB
        cur.execute("SELECT * FROM queue_table where queue=?", (queue,))
        row = cur.fetchone()
        if row is None:
            print("queue not found in queue_table")
        else:
            col_headers = [description[0] for description in cur.description]
            for key, val in zip(col_headers, row):
                print(key + ": " + str(val))
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def add_queue(conn, queue, min_nodes="", max_nodes="", max_time=""):
    try:
        insert_stmt = """
                      INSERT INTO queue_table (
                        queue,
                        min_nodes_per_job,
                        max_nodes_per_job,
                        max_time_per_job
                      ) VALUES (?, ?, ?, ?)
                      """
        conn.execute(
            insert_stmt,
            (
                queue,
                min_nodes,
                max_nodes,
                max_time,
            ),
        )

        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def delete_queue(conn, queue):
    delete_stmt = "DELETE FROM queue_table WHERE queue=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (queue,))

    conn.commit()


def edit_queue(
    conn, queue, min_nodes_per_job=None, max_nodes_per_job=None, max_time_per_job=None
):
    params = locals()
    editable_fields = ["min_nodes_per_job", "max_nodes_per_job", "max_time_per_job"]

    for field in editable_fields:
        if params[field] is not None:
            # check that the passed in value is truly an integer
            try:
                updated_value = int(params[field])
            except ValueError:
                print("passed in value must be an integer")

            # passing a value of -1 will clear any previously set limit
            if int(params[field]) == -1:
                update_stmt = "UPDATE queue_table SET " + field + "='' WHERE queue=?"
                conn.execute(
                    update_stmt,
                    (queue,),
                )
            else:
                update_stmt = "UPDATE queue_table SET " + field + "=? WHERE queue=?"
                conn.execute(
                    update_stmt,
                    (
                        params[field],
                        queue,
                    ),
                )

            # commit changes
            conn.commit()

    return 0
