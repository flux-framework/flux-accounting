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
def validate_columns(columns, valid_columns):
    """
    Validate a list of of columns against a list of valid columns of a table
    in a flux-accounting database.

    Args:
        columns: a list of column names
        valid_columns: a list of valid column names

    Raises:
        ValueError: at least one of the columns passed in is not valid
    """
    invalid_columns = [column for column in columns if column not in valid_columns]
    if invalid_columns:
        raise ValueError(f"invalid fields: {', '.join(invalid_columns)}")


def db_version(conn):
    """
    Return the DB schema version of the flux-accounting database.

    Args:
        conn: The SQLite Connection object.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")

    return cur.fetchone()[0]
