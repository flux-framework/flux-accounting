#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import fluxacct.accounting
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql

###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################
def view_factor(conn, factor, json_fmt=False, format_string=""):
    """
    View the integer weight for a particular priority factor in the plugin.

    Args:
        conn: the SQLite Connection object.
        factor: the name of the priority factor.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM priority_factor_weight_table WHERE factor=?", (factor,))
    formatter = fmt.PriorityFactorFormatter(cur, factor)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()


def edit_factor(conn, factor, weight):
    """
    Edit the integer weight for a particular priority factor in the plugin.

    Args:
        conn: the SQLite Connection object.
        factor: the name of the priority factor.
        weight: the new integer weight associated with the priority factor.
    """
    if factor not in fluxacct.accounting.PRIORITY_FACTORS:
        raise ValueError(
            f"factor {factor} not found in priority_factor_weight_table; "
            f"available factors are {','.join(fluxacct.accounting.PRIORITY_FACTORS)}"
        )
    cur = conn.cursor()
    cur.execute(
        "UPDATE priority_factor_weight_table SET weight=? WHERE factor=?",
        (
            weight,
            factor,
        ),
    )
    conn.commit()

    return 0


def list_factors(conn, cols=None, json_fmt=False, format_string=""):
    """
    List all factors in priority_factor_weight_table.

    Args:
        cols: a list of columns from the table to include in the output. By default, all
            columns are included.
        json_fmt: output data in JSON format. By default, the format of any returned data
            returned data is in a table format.
        format_string: a format string defining how each row should be formatted. Column
            names should be used as placeholders.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.PRIORITY_FACTOR_WEIGHTS_TABLE

    cur = conn.cursor()

    sql.validate_columns(cols, fluxacct.accounting.PRIORITY_FACTOR_WEIGHTS_TABLE)
    # construct SELECT statement
    select_stmt = f"SELECT {', '.join(cols)} FROM priority_factor_weight_table"
    cur.execute(select_stmt)

    # initialize AccountingFormatter object
    formatter = fmt.AccountingFormatter(cur)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()


def reset_factors(conn):
    """
    Reset the configuration for the priority factors in priority_factor_weight_table
    by re-inserting the factors and their original weight back in the database.

    Args:
        conn: the SQLite Connection object.
    """
    cur = conn.cursor()

    cur.execute(
        f"INSERT INTO priority_factor_weight_table (factor, weight) "
        f"VALUES ('fairshare', {fluxacct.accounting.FSHARE_WEIGHT_DEFAULT}) "
        f"ON CONFLICT(factor) DO UPDATE SET weight = excluded.weight;"
    )
    cur.execute(
        f"INSERT INTO priority_factor_weight_table (factor, weight) "
        f"VALUES ('queue', {fluxacct.accounting.QUEUE_WEIGHT_DEFAULT}) "
        f"ON CONFLICT(factor) DO UPDATE SET weight = excluded.weight;"
    )
    cur.execute(
        f"INSERT INTO priority_factor_weight_table (factor, weight) "
        f"VALUES ('bank', {fluxacct.accounting.BANK_WEIGHT_DEFAULT}) "
        f"ON CONFLICT(factor) DO UPDATE SET weight = excluded.weight;"
    )
    cur.execute(
        f"INSERT INTO priority_factor_weight_table (factor, weight) "
        f"VALUES ('urgency', {fluxacct.accounting.URGENCY_WEIGHT_DEFAULT}) "
        f"ON CONFLICT(factor) DO UPDATE SET weight = excluded.weight;"
    )

    conn.commit()
    return 0
