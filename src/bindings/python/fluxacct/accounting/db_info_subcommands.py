#!/usr/bin/env python3

###############################################################
# Copyright 2024 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import csv


def export_db_info(conn, users=None, banks=None):
    try:
        cur = conn.cursor()
        select_users_stmt = """
            SELECT username, userid, bank, shares, max_running_jobs, max_active_jobs,
            max_nodes, queues FROM association_table
        """
        cur.execute(select_users_stmt)
        table = cur.fetchall()

        # open a .csv file for writing
        users_filepath = users if users else "users.csv"
        users_file = open(users_filepath, "w")
        with users_file:
            writer = csv.writer(users_file)

            for row in table:
                writer.writerow(row)

        select_banks_stmt = """
            SELECT bank, parent_bank, shares FROM bank_table
        """
        cur.execute(select_banks_stmt)
        table = cur.fetchall()

        banks_filepath = banks if banks else "banks.csv"
        banks_file = open(banks_filepath, "w")
        with banks_file:
            writer = csv.writer(banks_file)

            for row in table:
                writer.writerow(row)
    except IOError as err:
        print(err)
