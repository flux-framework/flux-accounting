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


def view_qos(conn, qos):
    cur = conn.cursor()
    try:
        # get the information pertaining to a QOS in the DB
        cur.execute("SELECT * FROM qos_table where qos=?", (qos,))
        row = cur.fetchone()
        if row is None:
            print("QOS not found in qos_table")
        else:
            print(row)
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def add_qos(conn, qos, priority):
    try:
        insert_stmt = "INSERT INTO qos_table (qos, priority) VALUES (?, ?)"
        conn.execute(
            insert_stmt,
            (
                qos,
                priority,
            ),
        )

        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


# WARNING: deleting QOS entries does not remove them from the association_table,
# which could lead to inconsistencies when users submit jobs under that QOS.
def delete_qos(conn, qos):
    delete_stmt = "DELETE FROM qos_table WHERE qos=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (qos,))

    conn.commit()


def edit_qos(conn, qos, new_priority):
    edit_stmt = "UPDATE qos_table SET priority=? WHERE qos=?"

    # edit priority in qos_table
    conn.execute(
        edit_stmt,
        (
            new_priority,
            qos,
        ),
    )
    # commit changes
    conn.commit()
