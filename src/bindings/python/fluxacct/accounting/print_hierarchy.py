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
import sys
import pandas as pd

# this will print the full hierarchy of banks
# and associations that are found in the
# flux-accounting DB
def print_full_hierarchy(conn):
    hierarchy = "Bank|User|RawShares\n"

    # get the root bank in the bank table
    select_stmt = """
        SELECT bank_table.bank,
        bank_table.shares
        FROM bank_table
        WHERE parent_bank="";
        """
    dataframe = pd.read_sql_query(select_stmt, conn)

    try:
        if len(dataframe) == 0:
            raise IndexError("No root bank found")
        if len(dataframe) > 1:
            raise IndexError("More than one root bank found")
    except IndexError as exception:
        print(exception)
        sys.exit(1)

    root = dataframe.iloc[0]

    # helper function to traverse the bank hierarchy tree
    def get_sub_banks(row, indent=""):
        nonlocal hierarchy
        hierarchy += indent + row["bank"] + "||" + str(row["shares"]) + "\n"

        # get all sub banks of the current bank
        select_stmt = """
            SELECT bank_table.bank,
            bank_table.shares
            FROM bank_table
            WHERE parent_bank=?;
            """
        dataframe = pd.read_sql_query(select_stmt, conn, params=(row["bank"],))

        # we've reached a bank with no sub banks, so print
        # out all associations under this sub bank
        if len(dataframe) == 0:
            select_stmt = """
                SELECT association_table.username,
                association_table.shares,
                association_table.bank
                FROM association_table
                WHERE association_table.bank=?
                """
            dataframe = pd.read_sql_query(select_stmt, conn, params=(row["bank"],))
            for _, association_row in dataframe.iterrows():
                hierarchy += (
                    " "
                    + indent
                    + association_row["bank"]
                    + "|"
                    + association_row["username"]
                    + "|"
                    + str(association_row["shares"])
                    + "\n"
                )
        # this bank has sub banks, so call this helper
        # function again with the first sub bank it found
        else:
            for _, sub_bank_row in dataframe.iterrows():
                get_sub_banks(sub_bank_row, indent + " ")

    get_sub_banks(root)

    return hierarchy
