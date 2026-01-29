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
import pwd
import logging
import functools
import contextlib

from flux.constants import FLUX_USERID_UNKNOWN
from flux.util import parse_datetime
import fluxacct.accounting


def get_uid(username):
    """
    Get the userid for a given username. If the userid cannot be found, just return
    the username.

    Args:
        username: The username.
    """
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return FLUX_USERID_UNKNOWN


def get_username(userid):
    """
    Get the username for a given userid. If the username cannot be found, just return
    the userid as a string.
    """
    try:
        return pwd.getpwuid(userid).pw_name
    except KeyError:
        return str(userid)


def parse_timestamp(timestamp):
    """
    Parse a timestamp and convert it to a seconds-since-epoch timestamp. Try to first
    parse it as a human-readable format (e.g. "2025-01-27 12:00:00"), or just return as a
    seconds-since-epoch timestamp if the parsing fails.

    Returns:
        a seconds-since-epoch timestamp
    """
    try:
        # try to parse as a human-readable timestamp
        return parse_datetime(str(timestamp)).timestamp()
    except ValueError:
        # just return as a seconds-since-epoch timestamp
        return timestamp


def format_value(val):
    """
    Replace a max value in the database with a string.

    Args:
        val: the value being evaluated
    """
    if val == fluxacct.accounting.INTEGER_MAX:
        return "unlimited"
    return val


def config_logging(verbosity, logger):
    """
    Configure the logging level for a logger.

    Args:
        verbosity: the level of verbosity to set the logger to.
        logger: the logger object.
    """
    log_level = logging.WARNING
    if verbosity > 0:
        log_level = logging.INFO
    if verbosity > 1:
        log_level = logging.DEBUG
    logger.setLevel(log_level)
    # also set level on fluxacct package
    logging.getLogger(fluxacct.__name__).setLevel(log_level)


def with_cursor(func):
    """
    Decorator that automatically manages a Cursor object's lifecycle.

    The decorated function should take the Cursor object as its first parameter
    after the Connection object.
    """

    @functools.wraps(func)
    def wrapper(conn, *args, **kwargs):
        with contextlib.closing(conn.cursor()) as cur:
            return func(conn, cur, *args, **kwargs)

    return wrapper


def update_parent_bank_usage(conn, bank):
    """
    Recursively update the job_usage for a bank's parent banks up to the root.

    This function should be called after a leaf bank's job_usage has been updated.
    It will propagate the changes up through the hierarchy.

    Args:
        conn: The SQLite Connection object.
        bank: The name of the bank whose parents need updating.
    """
    cur = conn.cursor()

    cur.execute("SELECT parent_bank FROM bank_table WHERE bank=?", (bank,))
    result = cur.fetchone()

    if result is None:
        return

    parent_bank = result[0]

    if parent_bank == "":
        # reached the root bank (no parent); stop recursion
        return

    # calculate the total usage of all sub-banks under the parent
    cur.execute(
        "SELECT SUM(job_usage) FROM bank_table WHERE parent_bank=?", (parent_bank,)
    )
    total_usage = cur.fetchone()[0] or 0.0

    # update the parent bank's usage
    cur.execute(
        "UPDATE bank_table SET job_usage=? WHERE bank=?", (total_usage, parent_bank)
    )
    conn.commit()

    # recursively update the parent's parent
    update_parent_bank_usage(conn, parent_bank)
