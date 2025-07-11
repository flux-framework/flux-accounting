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

import fluxacct.accounting
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql


def view_queue(conn, queue, parsable=False, format_string=""):
    cur = conn.cursor()
    # get the information pertaining to a queue in the DB
    cur.execute("SELECT * FROM queue_table where queue=?", (queue,))

    formatter = fmt.QueueFormatter(cur, queue)

    if format_string != "":
        return formatter.as_format_string(format_string)
    if parsable:
        return formatter.as_table()
    return formatter.as_json()


def add_queue(
    conn,
    queue,
    min_nodes_per_job=1,
    max_nodes_per_job=1,
    max_time=60,
    priority=0,
    max_running_jobs=100,
    max_nodes=2147483647,
):
    try:
        insert_stmt = """
                      INSERT INTO queue_table (
                        queue,
                        min_nodes_per_job,
                        max_nodes_per_job,
                        max_time_per_job,
                        priority,
                        max_running_jobs,
                        max_nodes
                      ) VALUES (?, ?, ?, ?, ?, ?, ?)
                      """
        conn.execute(
            insert_stmt,
            (
                queue,
                min_nodes_per_job,
                max_nodes_per_job,
                max_time,
                priority,
                max_running_jobs,
                max_nodes,
            ),
        )

        conn.commit()

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError:
        raise sqlite3.IntegrityError(f"queue {queue} already exists in queue_table")


def delete_queue(conn, queue):
    """
    Remove a queue from the queue_table. If any associations still have permissions
    to this queue, issue a warning that the queue is still referenced elsewhere in the
    DB.
    """
    cursor = conn.cursor()
    # look for any rows in the association_table that reference this queue
    select_stmt = "SELECT * FROM association_table WHERE queues LIKE ?"
    cursor.execute(select_stmt, ("%" + queue + "%",))
    result = cursor.fetchall()
    warning_stmt = (
        "WARNING: user(s) in the association_table still "
        "reference this queue. Make sure to edit user rows to "
        "account for this deleted queue."
    )

    delete_stmt = "DELETE FROM queue_table WHERE queue=?"
    cursor.execute(delete_stmt, (queue,))
    conn.commit()

    if len(result) > 0:
        # at least one association references this queue; return warning message
        return warning_stmt

    return 0


def edit_queue(
    conn,
    queue,
    min_nodes_per_job=None,
    max_nodes_per_job=None,
    max_time_per_job=None,
    priority=None,
    max_running_jobs=None,
    max_nodes=None,
):
    params = locals()
    editable_fields = [
        "min_nodes_per_job",
        "max_nodes_per_job",
        "max_time_per_job",
        "priority",
        "max_running_jobs",
        "max_nodes",
    ]

    for field in editable_fields:
        if params[field] is not None:
            # check that the passed in value is truly an integer
            if not isinstance(params[field], int):
                raise ValueError("passed in value must be an integer")

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


def list_queues(conn, cols=None, json_fmt=False, format_string=""):
    """
    List all queues in queue_table.

    Args:
        cols: a list of columns from the table to include in the output. By default, all
            columns are included.
        table: output data in bank_table in table format. By default, the format of any
            returned data is in JSON.
        format_string: a format string defining how each row should be formatted. Column
            names should be used as placeholders.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.QUEUE_TABLE

    cur = conn.cursor()

    sql.validate_columns(cols, fluxacct.accounting.QUEUE_TABLE)
    # construct SELECT statement
    select_stmt = f"SELECT {', '.join(cols)} FROM queue_table"
    cur.execute(select_stmt)

    # initialize AccountingFormatter object
    formatter = fmt.AccountingFormatter(cur)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()
