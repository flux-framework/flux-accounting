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

from fluxacct.accounting import jobs_table_subcommands as j

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


def get_last_job_ts(acct_conn, user, bank):
    """
    Fetch the timestamp of the most recent inactive job for the association.
    This timestamp will be used in future queries to filter jobs that have run
    after this time.
    """
    s_ts = """
        SELECT last_job_timestamp FROM job_usage_factor_table WHERE username=? AND bank=?
        """
    cur = acct_conn.cursor()
    cur.execute(
        s_ts,
        (
            user,
            bank,
        ),
    )
    row = cur.fetchone()
    return float(row[0])


def fetch_usg_bins(acct_conn, user=None, bank=None):
    past_usage_factors = []

    select_stmt = "SELECT * from job_usage_factor_table WHERE username=? AND bank=?"
    cur = acct_conn.cursor()
    cur.execute(
        select_stmt,
        (
            user,
            bank,
        ),
    )
    row = cur.fetchone()

    for val in row[4:]:
        if isinstance(val, float):
            past_usage_factors.append(val)

    return past_usage_factors


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


def apply_decay_factor(decay, acct_conn, user=None, bank=None):
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
    usg_past = []
    usg_past_decay = []

    usg_past = fetch_usg_bins(acct_conn, user, bank)

    # apply decay factor to past usage periods of a user's jobs
    for power, usage_factor in enumerate(usg_past, start=1):
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


def get_curr_usg_bin(acct_conn, user, bank):
    """Fetch the current job usage factor value for a given association."""
    s_usg = """
        SELECT usage_factor_period_0 FROM job_usage_factor_table
        WHERE username=? AND bank=?
        """
    cur = acct_conn.cursor()
    cur.execute(
        s_usg,
        (
            user,
            bank,
        ),
    )
    row = cur.fetchone()
    return float(row[0])


def calc_usage_factor(conn, pdhl, user, bank, default_bank, end_hl):

    # hl_period represents the number of seconds that represent one usage bin
    hl_period = pdhl * 604800

    # get jobs that have completed since the last seen completed job
    last_j_ts = get_last_job_ts(conn, user, bank)
    user_jobs = j.filter_jobs_by_association(
        conn,
        bank,
        default_bank,
        user=user,
        after_start_time=last_j_ts,
    )

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
        usg_past = fetch_usg_bins(conn, user, bank)

        usg_historical = sum(usg_past)
    elif len(user_jobs) == 0 and (float(end_hl) < (time.time() - hl_period)):
        # no new jobs in the new half-life period; previous job usage periods need
        # to have a half-life decay applied to them
        usg_historical = apply_decay_factor(0.5, conn, user, bank)

        update_curr_usg_col(conn, usg_current, user, bank)
        update_hist_usg_col(conn, usg_historical, user, bank)
    elif (last_t_inactive - float(end_hl)) < hl_period:
        # found new jobs in the current half-life period; we need to 1) add the
        # new jobs to the current usage period, and 2) update the historical usage
        # period
        usg_current += get_curr_usg_bin(conn, user, bank)

        # usage_user_past = sum of the older usage factors
        usg_past = fetch_usg_bins(conn, user, bank)

        usg_historical = usg_current + sum(usg_past[1:])

        update_curr_usg_col(conn, usg_current, user, bank)
        update_hist_usg_col(conn, usg_historical, user, bank)
    else:
        # found new jobs in the new half-life period

        # apply decay factor to past usage periods of a user's jobs
        usg_past = apply_decay_factor(0.5, conn, user, bank)
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


def calc_bank_usage(acct_conn, cur, bank):
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
        total_usage = calc_bank_usage(acct_conn, cur, bank)
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

    cur = acct_conn.cursor()
    # fetch timestamp of the end of the current half-life period
    s_end_hl = """
        SELECT end_half_life_period FROM t_half_life_period_table WHERE cluster='cluster'
        """
    cur.execute(s_end_hl)
    row = cur.fetchone()
    end_hl = row[0]

    # begin transaction for all of the updates in the DB
    acct_conn.execute("BEGIN TRANSACTION")

    s_assoc = "SELECT username, bank, default_bank FROM association_table"
    cur = acct_conn.cursor()
    cur.execute(s_assoc)
    result = cur.fetchall()

    # update the job usage for every user in the association_table
    for row in result:
        calc_usage_factor(acct_conn, pdhl, row[0], row[1], row[2], end_hl)

    # find the root bank in the flux-accounting database
    s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
    cur.execute(s_root_bank)
    result = cur.fetchall()
    parent_bank = result[0][0]  # store the name of the root bank

    # update the job usage for every bank in the bank_table
    calc_parent_bank_usage(acct_conn, cur, parent_bank)

    check_end_hl(acct_conn, pdhl)

    # commit the transaction after the updates are finished
    acct_conn.commit()
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
