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
import sqlite3

import fluxacct.accounting
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import sql_util as sql


def export_db_info(conn, users=None, banks=None, bank_cols=None, user_cols=None):
    """
    Export information from association_table and bank_table and place them into .csv
    files. If the "users" or "banks" optional arguments are not specified, "users.csv"
    and "banks.csv" will be created and placed in the current working directory.

    Args:
        users: an optional specified path to a .csv file to hold all user information.

        banks: an optional specified path to a .csv file to hold all bank information.
    """
    # use all column names if none are passed in
    bank_cols = bank_cols or fluxacct.accounting.BANK_TABLE
    user_cols = user_cols or fluxacct.accounting.ASSOCIATION_TABLE
    try:
        # validate custom columns if any were passed in; execute queries to get DB info
        cur = conn.cursor()
        sql.validate_columns(user_cols, fluxacct.accounting.ASSOCIATION_TABLE)
        select_stmt = f"SELECT {', '.join(user_cols)} FROM association_table"
        cur.execute(select_stmt)
        association_table = cur.fetchall()
        association_table_headers = [description[0] for description in cur.description]

        sql.validate_columns(bank_cols, fluxacct.accounting.BANK_TABLE)
        select_stmt = f"SELECT {', '.join(bank_cols)} FROM bank_table"
        cur.execute(select_stmt)
        bank_table = cur.fetchall()
        bank_table_headers = [description[0] for description in cur.description]

        # open .csv files for writing
        users_file = open(users if users else "users.csv", "w")
        with users_file:
            writer = csv.writer(users_file)
            writer.writerow(association_table_headers)
            for row in association_table:
                writer.writerow(row)

        banks_file = open(banks if banks else "banks.csv", "w")
        with banks_file:
            writer = csv.writer(banks_file)
            writer.writerow(bank_table_headers)
            for row in bank_table:
                writer.writerow(row)
    except ValueError as err:
        raise ValueError(f"export-db: {err}")
    except IOError as err:
        raise IOError(f"export-db: {err}")
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(
            f"export-db: an sqlite3.OperationalError occurred: {exc}"
        )


def populate_db(conn, users=None, banks=None):
    if banks is not None:
        try:
            with open(banks) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=",")

                for row in csv_reader:
                    b.add_bank(
                        conn,
                        bank=row[0],
                        parent_bank=row[1],
                        shares=row[2],
                    )
        except IOError as err:
            print(err)

    if users is not None:
        try:
            with open(users) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=",")

                # assign default values to fields if
                # their slot is empty in the csv file
                for row in csv_reader:
                    username = row[0]
                    uid = row[1]
                    bank = row[2]
                    shares = row[3] if row[3] != "" else 1
                    max_running_jobs = row[4] if row[4] != "" else 5
                    max_active_jobs = row[5] if row[5] != "" else 7
                    max_nodes = row[6] if row[6] != "" else 2147483647
                    queues = row[7]

                    u.add_user(
                        conn,
                        username,
                        bank,
                        uid,
                        shares,
                        max_running_jobs,
                        max_active_jobs,
                        max_nodes,
                        queues,
                    )
        except IOError as err:
            print(err)
