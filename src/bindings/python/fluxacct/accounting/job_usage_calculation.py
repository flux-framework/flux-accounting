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
import math
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting import util

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


def update_t_inactive(acct_conn, last_t_inactive, user, bank):
    """
    Save the timestamp of the most recent inactive job for the association.
    """
    u_ts = """
        UPDATE job_usage_factor_table SET last_job_timestamp=? WHERE username=? AND bank=?
        """
    acct_conn.execute(
        u_ts,
        (
            last_t_inactive,
            user,
            bank,
        ),
    )


def update_hist_usg_col(acct_conn, usg_h, user, bank):
    """Update the job_usage column for the association."""
    u_usg = """
        UPDATE association_table SET job_usage=? WHERE username=? AND bank=?
        """
    acct_conn.execute(
        u_usg,
        (
            usg_h,
            user,
            bank,
        ),
    )


def update_curr_usg_col(acct_conn, usg_h, user, bank):
    """
    Write the current job usage factor for the association to the
    job_usage_factor_table.
    """
    u_usg_factor = """
        UPDATE job_usage_factor_table SET usage_factor_period_0=? WHERE username=? AND bank=?
        """
    acct_conn.execute(
        u_usg_factor,
        (
            usg_h,
            user,
            bank,
        ),
    )


def apply_decay_factor(decay, acct_conn, user, bank, usage_factors):
    """
    Apply a decay factor to an association's job usage period values. Since this helper
    issues a write to the flux-accounting DB and does not have a .commit() call after the
    update, this function should be called inside of a SQLite TRANSACTION.

    Args:
        decay: The decay factor to be applied to every job usage period.
        acct_conn: The SQLite Connection object.
        user: The username of the association.
        bank: The bank name of the association.
    """
    usg_past_decay = []

    # apply decay factor to past usage periods of a user's jobs
    for power, usage_factor in enumerate(usage_factors, start=1):
        usg_past_decay.append(usage_factor * math.pow(decay, power))

    # update job_usage_factor_table with new values, starting with the second usage
    # period and working back to the oldest usage period since the most recent usage
    # period is updated separately
    period = 1
    for usage_factor in usg_past_decay[0:-1]:
        update_stmt = (
            "UPDATE job_usage_factor_table SET usage_factor_period_"
            + str(period)
            + "=? WHERE username=? AND bank=?"
        )
        acct_conn.execute(
            update_stmt,
            (
                str(usage_factor),
                user,
                bank,
            ),
        )
        period += 1

    # only return the usage factors up to but not including the oldest one
    # since it no longer affects a user's historical usage factor
    return sum(usg_past_decay[:-1])


def calc_usage_factor(
    conn,
    pdhl,
    user,
    bank,
    end_hl,
    usage_factors,
    user_jobs,
):

    # hl_period represents the number of seconds that represent one usage bin
    hl_period = pdhl * 604800

    last_t_inactive = 0.0
    usg_current = 0.0

    if len(user_jobs) > 0:
        user_jobs.sort(key=lambda job: job.t_inactive)

        per_job_factors = []
        for job in user_jobs:
            per_job_factors.append(round((job.nnodes * job.elapsed), 5))

        last_t_inactive = user_jobs[-1].t_inactive
        usg_current = sum(per_job_factors)

        update_t_inactive(conn, last_t_inactive, user, bank)

    if len(user_jobs) == 0 and (float(end_hl) > (time.time() - hl_period)):
        # no new jobs in the current half-life period; the job usage for the
        # association stays exactly the same
        usg_historical = sum(usage_factors)
    elif len(user_jobs) == 0 and (float(end_hl) < (time.time() - hl_period)):
        # no new jobs in the new half-life period; previous job usage periods need
        # to have a half-life decay applied to them
        usg_historical = apply_decay_factor(0.5, conn, user, bank, usage_factors)

        update_curr_usg_col(conn, usg_current, user, bank)
        update_hist_usg_col(conn, usg_historical, user, bank)
    elif (last_t_inactive - float(end_hl)) < hl_period:
        # found new jobs in the current half-life period; we need to 1) add the
        # new jobs to the current usage period, and 2) update the historical usage
        # period
        usg_current += usage_factors[0]
        usg_historical = usg_current + sum(usage_factors[1:])

        update_curr_usg_col(conn, usg_current, user, bank)
        update_hist_usg_col(conn, usg_historical, user, bank)
    else:
        # found new jobs in the new half-life period
        # apply decay factor to past usage periods of a user's jobs
        usg_past = apply_decay_factor(0.5, conn, user, bank, usage_factors)
        usg_historical = usg_current + usg_past

        update_curr_usg_col(conn, usg_historical, user, bank)
        update_hist_usg_col(conn, usg_historical, user, bank)

    return usg_historical


def check_end_hl(acct_conn, pdhl):
    hl_period = pdhl * 604800

    cur = acct_conn.cursor()

    # fetch timestamp of the end of the current half-life period
    s_end_hl = """
        SELECT end_half_life_period
        FROM t_half_life_period_table
        WHERE cluster='cluster'
        """
    cur.execute(s_end_hl)
    row = cur.fetchone()
    end_hl = row[0]

    if float(end_hl) < (time.time() - hl_period):
        # update new end of half-life period timestamp
        update_timestamp_stmt = """
            UPDATE t_half_life_period_table
            SET end_half_life_period=?
            WHERE cluster='cluster'
            """
        acct_conn.execute(update_timestamp_stmt, ((float(end_hl) + hl_period),))


def calc_bank_usage(cur, bank):
    # fetch the job_usage value for every user under the passed-in bank
    s_associations = "SELECT job_usage FROM association_table WHERE bank=?"
    cur.execute(s_associations, (bank,))
    job_usage_list = cur.fetchall()

    total_usage = 0.0
    if job_usage_list:
        # aggregate job usage for bank
        for job_usage in job_usage_list:
            total_usage += job_usage[0]

    # update the bank_table with the total job usage for the bank
    u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
    cur.execute(
        u_job_usage,
        (
            total_usage,
            bank,
        ),
    )

    return total_usage


def calc_parent_bank_usage(acct_conn, cur, bank):
    # find all sub-banks of the current bank
    cur.execute("SELECT bank FROM bank_table WHERE parent_bank=?", (bank,))
    sub_banks = cur.fetchall()

    total_usage = 0.0
    if len(sub_banks) == 0:
        # we've reached a bank with no sub banks, so take the usage from that bank
        # and add it to the total usage for the parent bank
        total_usage = calc_bank_usage(cur, bank)
    else:
        # for each sub bank, keep traversing to find the usage for
        # each bank with users in it
        for sub_bank in sub_banks:
            sub_usage = calc_parent_bank_usage(acct_conn, cur, sub_bank[0])
            total_usage += sub_usage

    # update the usage for this bank itself
    u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
    cur.execute(u_job_usage, (total_usage, bank))

    return total_usage


def update_job_usage(acct_conn, pdhl=1):
    LOGGER.info(
        "beginning job-usage update for flux-accounting DB; "
        "slow response times may occur"
    )
    acct_conn.row_factory = sqlite3.Row
    cur = acct_conn.cursor()

    with acct_conn:
        # fetch timestamp of the end of the current half-life period
        s_end_hl = """
            SELECT end_half_life_period FROM t_half_life_period_table WHERE cluster='cluster'
            """
        cur.execute(s_end_hl)
        row = cur.fetchone()
        end_hl = row[0]

        # begin transaction for all of the updates in the DB
        acct_conn.execute("BEGIN TRANSACTION")
        s_assoc = """
            SELECT a.username, a.bank, a.default_bank, j.*
            FROM association_table a
            LEFT JOIN job_usage_factor_table j
            ON a.username = j.username AND a.bank = j.bank
            """
        cur.execute(s_assoc)
        result = cur.fetchall()

        # fetch new jobs for every association based on their last completed job
        s_new_jobs = """
            SELECT r.userid,r.id,r.t_submit,r.t_run,r.t_inactive,r.ranks,r.R,r.jobspec,
            r.project,r.bank,r.requested_duration,r.actual_duration,b.ignore_older_than
            FROM jobs r LEFT JOIN job_usage_factor_table j
            ON r.userid = j.userid AND r.bank = j.bank
            LEFT JOIN bank_table b
            ON r.bank = b.bank WHERE r.t_run > j.last_job_timestamp
            AND r.t_inactive > b.ignore_older_than
        """
        cur.execute(s_new_jobs)
        new_jobs = cur.fetchall()
        new_job_records = j.convert_to_obj(new_jobs)
        # convert new jobs to a dictionary where they key is a tuple of the user ID and bank
        # associated with the job
        association_jobs = defaultdict(list)
        for job in new_job_records:
            key = (job.userid, job.bank)
            association_jobs[key].append(job)

        # update the job usage for every user in the association_table
        for row in result:
            # add all of the job_usage_factor_period_* columns to dictionary
            usage_factors = []
            for key in row.keys():
                if key.startswith("usage_factor_period_"):
                    usage_factors.append(row[key])
            calc_usage_factor(
                conn=acct_conn,
                pdhl=pdhl,
                user=row["username"],
                bank=row["bank"],
                end_hl=end_hl,
                usage_factors=usage_factors,
                user_jobs=association_jobs[(row["userid"], row["bank"])],
            )

        # find the root bank in the flux-accounting database
        s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
        cur.execute(s_root_bank)
        result = cur.fetchall()
        parent_bank = result[0][0]  # store the name of the root bank

        # update the job usage for every bank in the bank_table
        calc_parent_bank_usage(acct_conn, cur, parent_bank)

        check_end_hl(acct_conn, pdhl)

        LOGGER.info("job-usage update for flux-accounting DB now complete")

        return 0


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
        fields="{username} {bank} {project} {nnodes} {t_run} {t_inactive}",
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
