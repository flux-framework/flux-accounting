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


def view_factor(conn, factor):
    cur = conn.cursor()
    try:
        # get the information pertaining to a plugin weight in the DB
        cur.execute("SELECT * FROM plugin_factor_table WHERE factor=?", (factor,))
        rows = cur.fetchall()
        headers = [description[0] for description in cur.description]
        if not rows:
            print("Factor not found in plugin_factor_table")
        else:
            # print column names of plugin_factor_table
            for header in headers:
                print(header.ljust(18), end=" ")
            print()
            for row in rows:
                for col in list(row):
                    print(str(col).ljust(18), end=" ")
                print()
    except sqlite3.OperationalError as e_database_error:
        print(e_database_error)


def edit_factor(conn, factor, weight=None):
    try:
        update_stmt = "UPDATE plugin_factor_table SET weight=? WHERE factor=?"
        updated_weight = int(weight)  # check that the weight is of type int

        conn.execute(
            update_stmt,
            (
                weight,
                factor,
            ),
        )

        # commit changes
        conn.commit()
    except ValueError:
        raise ValueError("Weight must be an integer")
