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
import json

import flux
from flux.job.JobID import JobID
import fluxacct.accounting
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql

###############################################################
#                                                             #
#                          Classes                            #
#                                                             #
###############################################################
class Association:
    """
    An association (a tuple of username+bank) in the flux-accounting DB.
    Args:
        username: the username of the association.
        bank: the name of the bank of the association.
        fairshare: the association's fair-share value.
    """

    def __init__(self, username, bank, fairshare):
        self.username = username
        self.bank = bank
        self.fairshare = fairshare


class Bank:
    """
    A bank in the flux-accounting DB.
    Args:
        name: the name of the bank.
        priority: the priority associated with the bank.
    """

    def __init__(self, name, priority):
        self.name = name
        self.priority = priority


class Queue:
    """
    A queue in the flux-accounting DB.
    Args:
        name: the name of the queue.
        priority: the priority associated with the queue.
    """

    def __init__(self, name, priority):
        self.name = name
        self.priority = priority


###############################################################
#                                                             #
#                     Helper Functions                        #
#                                                             #
###############################################################
def initialize_associations(cur, username, bank=None):
    """
    Create Association objects to be used when generating output for the
    "jobs" command.

    Args:
        cur: A SQLite Cursor object used to execute a query.
        username: The username of the association.
        bank: The bank name of the association. If no bank is specified, the
            query will fetch every association that has the specified username.
    """
    associations = {}
    s_assocs = "SELECT username,bank,fairshare FROM association_table WHERE username=?"

    if bank is not None:
        s_assocs += " AND bank=?"
        cur.execute(
            s_assocs,
            (
                username,
                bank,
            ),
        )
    else:
        cur.execute(s_assocs, (username,))

    result = cur.fetchall()
    if not result:
        raise ValueError(f"could not find entry for {username} in association_table")

    for row in result:
        associations[(row["username"], row["bank"])] = Association(
            username=row["username"], bank=row["bank"], fairshare=row["fairshare"]
        )

    return associations


def initialize_banks(cur, bank=None):
    """
    Create Bank objects to be used when generating output for the "jobs"
    command.

    Args:
        cur: A SQLite Cursor object used to execute a query.
        bank: The bank name. If no bank is specified, the query will fetch
            every bank and its associated priority.
    """
    banks = {}
    s_bank_prio = "SELECT bank,priority FROM bank_table"

    if bank is not None:
        s_bank_prio += " WHERE bank=?"
        cur.execute(s_bank_prio, (bank,))
    else:
        cur.execute(s_bank_prio)

    result = cur.fetchall()
    if not result:
        raise ValueError(f"could not find entry for {bank} in bank_table")

    for row in result:
        banks[row["bank"]] = Bank(name=row["bank"], priority=row["priority"])

    return banks


def initialize_queues(cur, queue=None):
    """
    Create Queue objects to be used when generating output for the "jobs"
    command.

    Args:
        cur: A SQLite Cursor object used to execute a query.
        queue: The queue name. If no queue is specified, the query will fetch
            every queue and its associated priority.
    """
    queues = {}
    s_queue_prio = "SELECT queue,priority FROM queue_table"

    if queue is not None:
        s_queue_prio += " WHERE queue=?"
        cur.execute(s_queue_prio, (queue,))
    else:
        cur.execute(s_queue_prio)

    result = cur.fetchall()
    if not result:
        # the query failed to fetch any results; since queues might not be
        # configured in flux-accounting, just return an empty dict
        return {}

    for row in result:
        queues[row["queue"]] = Queue(name=row["queue"], priority=row["priority"])

    return queues


def as_format_string(column_names, rows, format_string):
    """
    Format a list of rows (as lists) using a format string and column names.

    Args:
        column_names: The names of the columns, used as format placeholders.
        rows: Rows of data.
        format_string: A format string with placeholders like {COLNAME}.
    """
    try:
        header = format_string.format(**{col: col for col in column_names})
        formatted_rows = [
            format_string.format(**dict(zip(column_names, row))) for row in rows
        ]
        return "\n".join([header] + formatted_rows)
    except KeyError as exc:
        raise ValueError(
            f"Invalid column name in format string: {exc.args[0]}.\n"
            f"Available columns: {', '.join(column_names)}"
        )


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


def job_priorities(
    conn,
    username,
    bank=None,
    queue=None,
    format_string=None,
    filters=None,
):
    """
    List a breakdown for the priority calculation for every active job for a given
    username. Filter the user's jobs by bank and/or by queue.
    Args:
        conn: the SQLite Connection object.
        username: the username of the association.
        bank: filter jobs by a bank.
        queue: filter jobs by a queue.
        format_string: optional format string for custom output.
        states: filter jobs by specific states.
    """
    handle = flux.Flux()
    cur = conn.cursor()

    # initialize all associations that have the username passed in and the
    # priority associated with any banks or queues (if no bank or queue is
    # passed in, *every* bank and queue's priority will be fetched)
    associations = initialize_associations(cur, username, bank)
    banks = initialize_banks(cur, bank)
    queues = initialize_queues(cur, queue)
    # fetch integer weight associated with each priority factor
    factors = list_factors(conn, json_fmt=True)
    priority_weights = {item["factor"]: item["weight"] for item in json.loads(factors)}

    joblist = (
        flux.job.JobList(handle, max_entries=0, user=username, queue=queue)
        if queue
        else flux.job.JobList(handle, max_entries=0, user=username)
    )
    if filters:
        for filt in filters.split(","):
            joblist.add_filter(filt)
    jobs = list(joblist.jobs())

    row_dicts = []
    for job in jobs:
        # the following if-condition will return all jobs (regardless of bank) if one
        # is not specified or will just filter jobs based on a specific bank since
        # JobList() does not filter on bank
        if bank is None or job.bank == bank:
            row = {
                "JOBID": JobID(job.id).f58,
                "USER": job.username,
                "BANK": job.bank,
                "BANKPRIO": banks[job.bank].priority,
                "BANKFACT": priority_weights.get("bank", 0),
                "QUEUE": job.queue,
                # if queues are not configured in flux-accounting, the "queues" dict
                # will have no values in it, so we need to make sure that this has a
                # default of 0 to indicate it is not affecting a job's priority
                "QPRIO": getattr(queues.get(job.queue), "priority", 0),
                "QFACT": priority_weights.get("queue", 0),
                "FAIRSHARE": job.annotations.user.fairshare,
                "FSFACTOR": priority_weights.get("fairshare", 0),
                "URGENCY": job.urgency,
                "URGFACT": priority_weights.get("urgency", 0),
                "PRIORITY": job.priority,
            }
            row_dicts.append(row)

    if format_string:
        column_names = list(row_dicts[0].keys()) if row_dicts else []
        rows = [list(row.values()) for row in row_dicts]
        return as_format_string(column_names, rows, format_string)

    # use default formatting
    header = (
        f"{'JOBID':<15}{'USER':<9}"
        f"{'BANK':<8}{'BANKPRIO':<10}{'BANKFACT':<10}"
        f"{'QUEUE':<8}{'QPRIO':<7}{'QFACT':<7}"
        f"{'FAIRSHARE':<10}{'FSFACTOR':<10}"
        f"{'URGENCY':<8}{'URGFACT':<8}"
        f"{'PRIORITY':<8}"
    )
    rows = [
        f"{r['JOBID']:<15}{r['USER']:<9}"
        f"{r['BANK']:<8}{r['BANKPRIO']:<10}{r['BANKFACT']:<10}"
        f"{r['QUEUE']:<8}{r['QPRIO']:<7}{r['QFACT']:<7}"
        f"{r['FAIRSHARE']:<10}{r['FSFACTOR']:<10}"
        f"{r['URGENCY']:<8}{r['URGFACT']:<8}"
        f"{r['PRIORITY']:<8}"
        for r in row_dicts
    ]
    return f"{header}\n" + "\n".join(rows)
