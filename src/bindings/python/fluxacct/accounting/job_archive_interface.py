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
import pwd
import csv
import math
import json

from flux.resource import ResourceSet


def get_username(userid):
    try:
        return pwd.getpwuid(userid).pw_name
    except KeyError:
        return str(userid)


def get_uid(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def write_records_to_file(job_records, output_file):
    with open(output_file, "w", newline="") as csvfile:
        spamwriter = csv.writer(
            csvfile, delimiter="|", escapechar="'", quoting=csv.QUOTE_NONE
        )
        spamwriter.writerow(
            (
                "UserID",
                "Username",
                "JobID",
                "T_Submit",
                "T_Run",
                "T_Inactive",
                "Nodes",
                "R",
            )
        )
        for record in job_records:
            spamwriter.writerow(
                (
                    str(record.userid),
                    str(record.username),
                    str(record.jobid),
                    str(record.t_submit),
                    str(record.t_run),
                    str(record.t_inactive),
                    str(record.nnodes),
                    str(record.resources),
                )
            )


def fetch_job_records(job_records):
    job_record_str = []
    job_record_str.append(
        "{:<10} {:<10} {:<20} {:<20} {:<20} {:<20} {:<10}".format(
            "UserID",
            "Username",
            "JobID",
            "T_Submit",
            "T_Run",
            "T_Inactive",
            "Nodes",
        )
    )
    for record in job_records:
        job_record_str.append(
            "{:<10} {:<10} {:<20} {:<20} {:<20} {:<20} {:<10}".format(
                record.userid,
                record.username,
                record.jobid,
                record.t_submit,
                record.t_run,
                record.t_inactive,
                record.nnodes,
            )
        )

    return job_record_str


class JobRecord:
    """
    A record of an individual job.
    """

    def __init__(
        self, userid, _username, jobid, t_submit, t_run, t_inactive, nnodes, resources
    ):
        self.userid = userid
        self.username = get_username(userid)
        self.jobid = jobid
        self.t_submit = t_submit
        self.t_run = t_run
        self.t_inactive = t_inactive
        self.nnodes = nnodes
        self.resources = resources

    @property
    def elapsed(self):
        return self.t_inactive - self.t_run

    @property
    def queued(self):
        return self.t_run - self.t_submit


def add_job_records(rows):
    job_records = []

    for row in rows:
        rset = ResourceSet(row[6])  # fetch R

        job_record = JobRecord(
            row[0],  # userid
            get_username(row[0]),  # username
            row[1],  # jobid
            row[2],  # t_submit
            row[3],  # t_run
            row[4],  # t_inactive
            rset.nnodes,  # nnodes
            row[6],  # resources
        )
        job_records.append(job_record)

    return job_records


# check if 1) a "bank" attribute exists in jobspec, which means the user
# submitted a job under a secondary bank, and 2) the "bank" attribute
# in jobspec matches the bank we are currently counting jobs for
def check_jobspec(jobspec, bank):
    return bool(
        ("bank" in jobspec["attributes"]["system"])
        and (jobspec["attributes"]["system"]["bank"] == bank)
    )


# we are looking for jobs that were submitted under a secondary bank, so we'll
# only add jobs that have the same bank name attribute in the jobspec
def sec_bank_jobs(job_records, bank):
    jobs = []
    for job in job_records:
        jobspec = json.loads(job[7])

        if check_jobspec(jobspec, bank):
            jobs.append(job)

    return jobs


# we are looking for jobs that were submitted under a default bank, which has
# two cases: 1) the user submitted a job while specifying their default bank,
# or 2) the user submitted a job without specifying any bank at all
def def_bank_jobs(job_records, default_bank):
    jobs = []
    for job in job_records:
        jobspec = json.loads(job[7])

        if check_jobspec(jobspec, default_bank):
            jobs.append(job)
        elif "bank" not in jobspec["attributes"]["system"]:
            jobs.append(job)

    return jobs


def get_job_records(conn, bank, default_bank, **kwargs):
    # find out which args were passed and place them in a dict
    valid_params = {"user", "after_start_time", "before_end_time", "jobid"}
    params = {
        key: val
        for key, val in kwargs.items()
        if val is not None and key in valid_params
    }

    select_stmt = "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R,jobspec FROM jobs"
    where_clauses = []
    params_list = []

    if "user" in params:
        params["user"] = get_uid(params["user"])
        where_clauses.append("userid = ?")
        params_list.append(params["user"])
    if "after_start_time" in params:
        where_clauses.append("t_run > ?")
        params_list.append(params["after_start_time"])
    if "before_end_time" in params:
        where_clauses.append("t_inactive < ?")
        params_list.append(params["before_end_time"])
    if "jobid" in params:
        where_clauses.append("id = ?")
        params_list.append(params["jobid"])

    if where_clauses:
        select_stmt += " WHERE " + " AND ".join(where_clauses)

    cur = conn.cursor()
    cur.execute(select_stmt, tuple(params_list))
    result = cur.fetchall()

    if not result:
        return []

    if bank is None and default_bank is None:
        # special case for unit tests in test_job_archive_interface.py
        return add_job_records(result)
    
    if bank != default_bank:
        jobs = sec_bank_jobs(result, bank)
    else:
        jobs = def_bank_jobs(result, default_bank)

    job_records = add_job_records(jobs)

    return add_job_records(result)


def output_job_records(conn, output_file, **kwargs):
    job_record_str = ""
    job_records = get_job_records(conn, None, None, **kwargs)

    job_record_str = fetch_job_records(job_records)

    if output_file is None:
        return job_record_str

    write_records_to_file(job_records, output_file)

    return job_record_str


def update_t_inactive(acct_conn, last_t_inactive, user, bank):
    # write last seen t_inactive to last_job_timestamp for user
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
    # fetch timestamp of last seen job (gets jobs that have run after this time)
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
    # update job_usage column in association_table
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
    # write usage to first column in job_usage_factor_table
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
    usg_past = []
    usg_past_decay = []

    usg_past = fetch_usg_bins(acct_conn, user, bank)

    # apply decay factor to past usage periods of a user's jobs
    for power, usage_factor in enumerate(usg_past, start=1):
        usg_past_decay.append(usage_factor * math.pow(decay, power))

    # update job_usage_factor_table with new values, starting with period-2;
    # the last usage factor in the table will get discarded after the update
    period = 1
    for usage_factor in usg_past_decay[1 : len(usg_past_decay) - 1]:
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
    # append current usage to the first usage factor bin
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


def calc_usage_factor(conn, pdhl, user, bank, default_bank):

    # hl_period represents the number of seconds that represent one usage bin
    hl_period = pdhl * 604800

    cur = conn.cursor()

    # fetch timestamp of the end of the current half-life period
    s_end_hl = """
        SELECT end_half_life_period FROM t_half_life_period_table WHERE cluster='cluster'
        """
    cur.execute(s_end_hl)
    row = cur.fetchone()
    end_hl = row[0]

    # get jobs that have completed since the last seen completed job
    last_j_ts = get_last_job_ts(conn, user, bank)
    user_jobs = get_job_records(
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
        # no new jobs in the current half-life period
        usg_past = fetch_usg_bins(conn, user, bank)

        usg_historical = sum(usg_past)
    elif len(user_jobs) == 0 and (float(end_hl) < (time.time() - hl_period)):
        # no new jobs in the new half-life period
        usg_historical = apply_decay_factor(0.5, conn, user, bank)

        update_hist_usg_col(conn, usg_historical, user, bank)
    elif (last_t_inactive - float(end_hl)) < hl_period:
        # found new jobs in the current half-life period
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


def calc_parent_bank_usage(acct_conn, cur, bank, total_usage=0.0):
    # find all sub banks
    cur.execute("SELECT bank FROM bank_table WHERE parent_bank=?", (bank,))
    sub_banks = cur.fetchall()

    if len(sub_banks) == 0:
        # we've reached a bank with no sub banks, so take the usage from that bank
        # and add it to the total usage for the parent bank
        job_usage = calc_bank_usage(acct_conn, cur, bank)
        total_usage += job_usage
    else:
        # for each sub bank, keep traversing to find the usage for
        # each bank with users in it
        for sub_bank in sub_banks:
            total_usage = calc_parent_bank_usage(
                acct_conn, cur, sub_bank[0], total_usage
            )
            # update the bank_table with the total job usage
            u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
            cur.execute(
                u_job_usage,
                (
                    total_usage,
                    bank,
                ),
            )

    return total_usage


def update_job_usage(acct_conn, pdhl=1):
    # begin transaction for all of the updates in the DB
    acct_conn.execute("BEGIN TRANSACTION")

    s_assoc = "SELECT username, bank, default_bank FROM association_table"
    cur = acct_conn.cursor()
    cur.execute(s_assoc)
    result = cur.fetchall()

    # update the job usage for every user in the association_table
    for row in result:
        calc_usage_factor(acct_conn, pdhl, row[0], row[1], row[2])

    # find the root bank in the flux-accounting database
    s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
    cur.execute(s_root_bank)
    result = cur.fetchall()
    parent_bank = result[0][0]  # store the name of the root bank

    # update the job usage for every bank in the bank_table
    calc_parent_bank_usage(acct_conn, cur, parent_bank, 0.0)

    check_end_hl(acct_conn, pdhl)

    # commit the transaction after the updates are finished
    acct_conn.commit()

    return 0


# Scrub jobs from the flux-accounting "jobs" table by removing any
# record that is older than num_weeks old. If no number of weeks is
# specified, remove any record that is older than 6 months old.
def scrub_old_jobs(conn, num_weeks=26):
    cur = conn.cursor()
    # calculate total amount of time to go back (in terms of seconds)
    # (there are 604,800 seconds in a week)
    cutoff_time = time.time() - (num_weeks * 604800)

    # fetch all jobs that finished before this time
    select_stmt = "DELETE FROM jobs WHERE t_inactive < ?"
    cur.execute(select_stmt, (cutoff_time,))
    conn.commit()
