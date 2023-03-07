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
        rows = cur.fetchall()
        headers = [description[0] for description in cur.description]
        queue_str = ""
        if not rows:
            raise ValueError(f"Queue {queue} not found in queue_table")

        # print column names of queue_table
        for header in headers:
            queue_str += header.ljust(18)
        queue_str += "\n"
        for row in rows:
            for col in list(row):
                queue_str += str(col).ljust(18)
            queue_str += "\n"

        return queue_str
    except sqlite3.OperationalError as e_database_error:
        return e_database_error


def add_queue(conn, queue, min_nodes=1, max_nodes=1, max_time=60, priority=0):
    try:
        insert_stmt = """
                      INSERT INTO queue_table (
                        queue,
                        min_nodes_per_job,
                        max_nodes_per_job,
                        max_time_per_job,
                        priority
                      ) VALUES (?, ?, ?, ?, ?)
                      """
        conn.execute(
            insert_stmt,
            (
                queue,
                min_nodes,
                max_nodes,
                max_time,
                priority,
            ),
        )

        conn.commit()

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        return integrity_error


def delete_queue(conn, queue):
    delete_stmt = "DELETE FROM queue_table WHERE queue=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (queue,))

    conn.commit()

    return 0


def edit_queue(
    conn,
    queue,
    min_nodes_per_job=None,
    max_nodes_per_job=None,
    max_time_per_job=None,
    priority=None,
):
    params = locals()
    editable_fields = [
        "min_nodes_per_job",
        "max_nodes_per_job",
        "max_time_per_job",
        "priority",
    ]

    for field in editable_fields:
        if params[field] is not None:
            # check that the passed in value is truly an integer
            if not isinstance(params[field], int):
                try:
                    raise ValueError("passed in value must be an integer")
                except ValueError as val_err:
                    return f"error editing field for queue: {val_err}"

            update_stmt = "UPDATE queue_table SET " + field

            # passing a value of -1 will clear any previously set limit
            if int(params[field]) == -1:
                update_stmt += "=NULL WHERE queue=?"
                tup = (queue,)
            else:
                update_stmt += "=? WHERE queue=?"
                tup = (
                    params[field],
                    queue,
                )

            conn.execute(update_stmt, tup)

            # commit changes
            conn.commit()

    return 0
