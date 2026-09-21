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
import time
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from fluxacct.jobs import records as j
from fluxacct.jobs.calculators.base import JobUsageCalculator
from fluxacct.jobs.calculators.periodic import PeriodicUsageCalculator
from fluxacct import util
from fluxacct.util import with_cursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


def rebuild_project_usage(acct_conn):
    """Replace project totals with usage calculated from all retained jobs."""
    acct_conn.row_factory = sqlite3.Row
    cur = acct_conn.cursor()

    with acct_conn:
        node_weight, core_weight, gpu_weight = PeriodicUsageCalculator(
            acct_conn
        ).get_usage_weights()
        registered_projects = {
            row[0] for row in cur.execute("SELECT project FROM project_table")
        }
        cur.execute("""
            INSERT OR IGNORE INTO project_usage_state
                (project, last_job_timestamp)
            SELECT project, 0.0 FROM project_table
            """)
        cur.execute("""
            DELETE FROM project_usage_state
            WHERE project NOT IN (SELECT project FROM project_table)
            """)
        rows = cur.execute("""
            SELECT userid,id,t_submit,t_run,t_inactive,ranks,R,jobspec,project,
            bank,requested_duration,actual_duration FROM jobs
            ORDER BY id
            """)

        missing_project = 0
        invalid_resources = 0
        unregistered_projects = defaultdict(int)
        project_usage = defaultdict(float)
        project_timestamps = defaultdict(float)

        for row in rows:
            project = row["project"]
            if not project:
                # a project was not registered for this job; just skip it
                missing_project += 1
                continue
            if project not in registered_projects:
                # the project associated with this job could not be found in the
                # flux-accounting database; just skip it
                unregistered_projects[project] += 1
                continue

            project_timestamps[project] = max(
                project_timestamps[project], row["t_inactive"]
            )
            records = j.convert_to_obj([row])
            if not records:
                # the resources for this job could not be extracted; just skip it
                invalid_resources += 1
                continue
            project_usage[project] += JobUsageCalculator.calculate_weighted_usage(
                records[0],
                node_weight,
                core_weight,
                gpu_weight,
            )

        # since we are rebuilding project usage from scratch, clear the existing usage
        cur.execute("UPDATE project_table SET usage=0.0")
        cur.executemany(
            "UPDATE project_table SET usage=? WHERE project=?",
            [(usage, project) for project, usage in project_usage.items()],
        )
        cur.execute("UPDATE project_usage_state SET last_job_timestamp=0.0")
        cur.executemany(
            """
            UPDATE project_usage_state SET last_job_timestamp=? WHERE project=?
            """,
            [(timestamp, project) for project, timestamp in project_timestamps.items()],
        )

    if missing_project:
        LOGGER.warning(
            "skipped %d job(s) without a project during project-usage rebuild",
            missing_project,
        )
    for project, count in sorted(unregistered_projects.items()):
        LOGGER.warning(
            "project %r is not registered; skipped %d job(s)", project, count
        )
    if invalid_resources:
        LOGGER.warning(
            "skipped %d job(s) with unusable resource data during "
            "project-usage rebuild",
            invalid_resources,
        )

    return {
        "missing_project": missing_project,
        "invalid_resources": invalid_resources,
        "unregistered_projects": dict(unregistered_projects),
    }


def update_job_usage(acct_conn):
    return PeriodicUsageCalculator(acct_conn).update()


def scrub_old_jobs(conn, num_weeks=26):
    """
    Scrub jobs from the jobs table by removing any record that is older than
    num_weeks old. If no number of weeks is specified, remove any record that
    is older than 6 months old.
    """
    cur = conn.cursor()
    # calculate total amount of time to go back (in terms of seconds)
    # (there are 604,800 seconds in a week)
    cutoff_time = time.time() - (num_weeks * 604800)

    # fetch all jobs that finished before this time
    select_stmt = "DELETE FROM jobs WHERE t_inactive < ?"
    cur.execute(select_stmt, (cutoff_time,))
    conn.commit()

    return 0


def get_key(instr, rtype, auser, abank):
    """
    Return an appropriate hash key based on user requested report type, user, bank.

    Args:
        instr: The prefix for each line, which can be either be the association
            (in "bank:username" format) or "TOTAL".
        rtype: The resource type.
        auser: The username of the association.
        abank: The bank name of the association.
    """
    if instr == "TOTAL":
        return ""

    parts = instr.split(":")
    if len(parts) == 2:
        bank, user = parts
    else:
        return ""

    if (auser is not None and user != auser) or (abank is not None and bank != abank):
        return ""

    if rtype is not None and rtype == "bybank":
        return bank
    if rtype is not None and rtype == "byuser":
        return user
    return instr


def format_header(rtype, tunit, sizebins):
    """
    Return a formatted header line.

    Args:
        rtype: The resource type.
        tunit: The time unit.
        sizebins: The job size bins.
    """
    if rtype is not None:
        rtype = rtype.replace("by", "", 1)
    else:
        rtype = "association"

    if tunit is None:
        tunit = "sec"

    if len(sizebins) < 2:
        return "{:<26s}        total\n".format(rtype + "(node" + tunit + ")")
    szstr = ""
    for sizebin in sizebins:
        szstr += " {:>13d}+".format(sizebin)
    return "{:<24s}{}\n".format(rtype + "(node" + tunit + ")", szstr)


def format_line(key, data, tunit, sizebins):
    """
    Return a formatted data line.

    Args:
        key: The prefix of the line.
        data: The job usage value associated with the line.
        tunit: The time unit.
        sizebins: The job size bins.
    """
    divisor = 1
    if tunit is not None and tunit == "hour":
        divisor = 60 * 60
    elif tunit is not None and tunit == "min":
        divisor = 60

    datastr = ""
    for sizebin in sizebins:
        value = data.get(sizebin, 0)
        datastr += " {:>14.2f}".format(value / divisor)

    return "{:<24s}{}\n".format(key, datastr)


def view_usage_report(
    conn,
    start=None,
    end=None,
    user=None,
    bank=None,
    report_type=None,
    job_size_bins=None,
    time_unit=None,
):
    """
    Calculate a usage report for a user, bank, or association.

    Args:
        conn: The SQLite Connection object.
        start: Start date in the following format: YY/MM/DD
        end: End date in the following format: YY/MM/DD
        user: Only report data for a specific user.
        bank: Only report data for a specific bank.
        report_type: How the job data should be binned (by user, by bank, or by
            association).
        job_size_bins: A list of job sizes to bin data into.
        time_unit: The time unit used for calculating usage (per hour, minute, or
            second).
    """
    if start:
        start = util.parse_timestamp(start)
    else:
        # default to grabbing jobs from the last day
        yesterday = datetime.now() - timedelta(days=1)
        start = util.parse_timestamp(yesterday.strftime("%m/%d/%y"))

    if end:
        # end = process_timearg(end)
        end = util.parse_timestamp(end)
    else:
        # default to grabbing jobs up until right now
        today = datetime.now()
        end = util.parse_timestamp(today.strftime("%m/%d/%y"))

    # get job size bins
    sizebins = [0]
    if job_size_bins:
        if job_size_bins[0].isdigit():
            sizebins = [int(sz) for sz in job_size_bins.split(",")]
        else:
            sizebins = [0, 2, 8, 32, 128, 512, 2048, 8192]

    data = {}
    total = {}
    ktotal = {}

    result = j.view_jobs(
        conn,
        fields="{username} {bank} {nnodes} {t_run} {t_inactive}",
        after_start_time=(start - 7 * 24 * 60 * 60),
        before_end_time=end,
        user=user,
        bank=bank,
    )

    for i, line in enumerate(result.split("\n")):
        if i == 0:
            # skip header line
            continue
        if not line or not line[0].isalnum():
            continue

        parts = line.split()
        if len(parts) < 5:
            # could not find all necessary job attributes; skip this job
            continue

        username, bank, nnodes, t_run, t_inactive = (
            parts[0],
            parts[1],
            parts[2],
            parts[3],
            parts[4],
        )

        nnodes = int(nnodes)
        t_run = float(t_run)
        t_inactive = float(t_inactive)

        if t_inactive < start or t_inactive > end:
            # job is outside of the set time range; skip this job
            continue

        association = f"{bank}:{username}"
        key = get_key(association, report_type, username, bank)

        if key:
            jobusage = nnodes * (t_inactive - t_run)
            ktotal[key] = ktotal.get(key, 0) + jobusage

            for sizebin in reversed(sizebins):
                if nnodes >= sizebin:
                    if key not in data:
                        data[key] = {}
                    data[key][sizebin] = data[key].get(sizebin, 0) + jobusage
                    total[sizebin] = total.get(sizebin, 0) + jobusage
                    break

    result = ""
    result += format_header(report_type, time_unit, sizebins)

    for key in sorted(ktotal.keys(), key=lambda k: ktotal[k], reverse=True):
        result += format_line(key, data[key], time_unit, sizebins)

    result += format_line("TOTAL", total, time_unit, sizebins)

    return result


def clear_usage_period_columns(cur, bank):
    """
    Clear the job usage for the bank's job_usage_factor_* columns.

    Args:
        cur: The SQLite Cursor object.
        bank: The bank being cleared.
    """
    cur.execute(
        "UPDATE job_usage_per_association_table SET value=0.0 WHERE bank=?", (bank,)
    )
    cur.execute(
        "UPDATE job_usage_factor_table SET last_job_timestamp=0 WHERE bank=?", (bank,)
    )


@with_cursor
def clear_usage(conn, cur, banks, ignore_older_than=None):
    """
    Reset job usage for one or more banks in the flux-accounting database.

    Args:
        conn: The SQLite Connection object.
        banks: One or more banks to have its usage cleared.
        ignore_older_than: The timestamp in which all older jobs will not be considered
            towards job usage.
    """
    if len(banks) > 0:
        # one or more banks has been passed in to have their usage wiped
        for bank in banks:
            # first, reset the historical job usage for the bank
            cur.execute("UPDATE bank_table SET job_usage=0 WHERE bank=?", (bank,))
            # then reset usage/fair-share for all associations under this bank
            cur.execute(
                "UPDATE association_table SET job_usage=0 WHERE bank=?", (bank,)
            )
            cur.execute(
                "UPDATE association_table SET fairshare=0.5 WHERE bank=?", (bank,)
            )
            # reset all usage periods for associations under this bank
            clear_usage_period_columns(cur, bank)
            # propagate new usage up parent banks to root bank
            util.update_parent_bank_usage(conn, bank)
            if ignore_older_than is not None:
                # update bank_table with new ignore timestamp
                cur.execute(
                    "UPDATE bank_table SET ignore_older_than=? WHERE bank=?",
                    (
                        int(util.parse_timestamp(ignore_older_than)),
                        bank,
                    ),
                )
            else:
                # update bank_table with the current time to no longer consider any jobs
                # older than right now
                cur.execute(
                    "UPDATE bank_table SET ignore_older_than=? WHERE bank=?",
                    (
                        int(time.time()),
                        bank,
                    ),
                )
            # commit changes
            conn.commit()

    return 0
