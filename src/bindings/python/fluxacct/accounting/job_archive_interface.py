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

import pandas as pd


def count_ranks(ranks):
    if "-" in ranks:
        ranks_count = ranks.replace("-", ",").split(",")
        return int(ranks_count[1]) - int(ranks_count[0]) + 1

    return int(ranks) + 1


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
            csvfile, delimiter="|", quotechar="", escapechar="'", quoting=csv.QUOTE_NONE
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


def print_job_records(job_records):
    records = {}
    userid_arr = []
    username_arr = []
    jobid_arr = []
    t_submit_arr = []
    t_run_arr = []
    t_inactive_arr = []
    nnodes_arr = []
    r_arr = []

    for record in job_records:
        userid_arr.append(record.userid)
        username_arr.append(record.username)
        jobid_arr.append(record.jobid)
        t_submit_arr.append(record.t_submit)
        t_run_arr.append(record.t_run)
        t_inactive_arr.append(record.t_inactive)
        nnodes_arr.append(record.nnodes)
        r_arr.append(record.resources)

    records = {
        "UserID": userid_arr,
        "Username": username_arr,
        "JobID": jobid_arr,
        "T_Submit": t_submit_arr,
        "T_Run": t_run_arr,
        "T_Inactive": t_inactive_arr,
        "Nodes": nnodes_arr,
        "R": r_arr,
    }

    dataframe = pd.DataFrame(
        records,
        columns=[
            "UserID",
            "Username",
            "JobID",
            "T_Submit",
            "T_Run",
            "T_Inactive",
            "Nodes",
            "R",
        ],
    )
    pd.set_option("max_colwidth", 100)
    pd.set_option("display.float_format", lambda x: "%.5f" % x)
    print(dataframe)


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


def add_job_records(dataframe):
    job_records = []

    for _, row in dataframe.iterrows():
        job_record = JobRecord(
            row["userid"],
            get_username(row["userid"]),
            row["id"],
            row["t_submit"],
            row["t_run"],
            row["t_inactive"],
            count_ranks(row["ranks"]),
            row["R"],
        )
        job_records.append(job_record)

    return job_records


def view_job_records(conn, output_file, **kwargs):
    job_records = []

    # find out which args were passed and place them in a dict
    valid_params = ("user", "after_start_time", "before_end_time", "jobid")
    params = {}
    params_list = []

    params = {
        key: val
        for (key, val) in kwargs.items()
        if val is not None and key in valid_params
    }

    select_stmt = "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs "
    where_stmt = ""

    def append_to_where(where_stmt, conditional):
        if where_stmt != "":
            return "{} AND {} ".format(where_stmt, conditional)

        return "WHERE {}".format(conditional)

    # generate the SELECT statement based on the parameters passed in
    if "user" in params:
        params["user"] = get_uid(params["user"])
        params_list.append(params["user"])
        where_stmt = append_to_where(where_stmt, "userid=? ")
    if "after_start_time" in params:
        params_list.append(params["after_start_time"])
        where_stmt = append_to_where(where_stmt, "t_run > ? ")
    if "before_end_time" in params:
        params_list.append(params["before_end_time"])
        where_stmt = append_to_where(where_stmt, "t_inactive < ? ")
    if "jobid" in params:
        params_list.append(params["jobid"])
        where_stmt = append_to_where(where_stmt, "id=? ")

    select_stmt += where_stmt

    dataframe = pd.read_sql_query(select_stmt, conn, params=((*tuple(params_list),)))
    # if the length of dataframe is 0, that means
    # no job records were found in the jobs table,
    # so just return an empty list
    if len(dataframe.index) == 0:
        return job_records

    job_records = add_job_records(dataframe)
    if output_file is None:
        print_job_records(job_records)
    else:
        write_records_to_file(job_records, output_file)

    return job_records


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
    acct_conn.commit()


def get_last_job_ts(acct_conn, user, bank):
    # fetch timestamp of last seen job (gets jobs that have run after this time)
    s_ts = """
        SELECT last_job_timestamp FROM job_usage_factor_table WHERE username=? AND bank=?
        """
    timestamp = pd.read_sql_query(
        s_ts,
        acct_conn,
        params=(
            user,
            bank,
        ),
    )
    return float(timestamp.iloc[0])


def fetch_usg_bins(acct_conn, user=None, bank=None):
    past_usage_factors = []

    select_stmt = "SELECT * from job_usage_factor_table WHERE username=? AND bank=?"
    dataframe = pd.read_sql_query(
        select_stmt,
        acct_conn,
        params=(
            user,
            bank,
        ),
    )

    for val in dataframe.iloc[0].values[4:]:
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
    acct_conn.commit()


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
    acct_conn.commit()


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
        acct_conn.commit()
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
    dataframe = pd.read_sql_query(
        s_usg,
        acct_conn,
        params=(
            user,
            bank,
        ),
    )
    return float(dataframe.iloc[0])


def calc_usage_factor(jobs_conn, acct_conn, pdhl, user, bank):

    # hl_period represents the number of seconds that represent one usage bin
    hl_period = pdhl * 604800

    # fetch timestamp of the end of the current half-life period
    s_end_hl = """
        SELECT end_half_life_period FROM t_half_life_period_table WHERE cluster='cluster'
        """
    dataframe = pd.read_sql_query(s_end_hl, acct_conn)
    end_hl = dataframe.iloc[0]

    # get jobs that have completed since the last seen completed job
    last_j_ts = get_last_job_ts(acct_conn, user, bank)
    user_jobs = view_job_records(
        jobs_conn,
        output_file=None,
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

        update_t_inactive(acct_conn, last_t_inactive, user, bank)

    if len(user_jobs) == 0 and (float(end_hl) > (time.time() - hl_period)):
        # no new jobs in the current half-life period
        usg_past = fetch_usg_bins(acct_conn, user, bank)

        usg_historical = sum(usg_past)
    elif len(user_jobs) == 0 and (float(end_hl) < (time.time() - hl_period)):
        # no new jobs in the new half-life period
        usg_historical = apply_decay_factor(0.5, acct_conn, user, bank)

        update_hist_usg_col(acct_conn, usg_historical, user, bank)
    elif (last_t_inactive - float(end_hl)) < hl_period:
        # found new jobs in the current half-life period
        usg_current += get_curr_usg_bin(acct_conn, user, bank)

        # usage_user_past = sum of the older usage factors
        usg_past = fetch_usg_bins(acct_conn, user, bank)

        usg_historical = usg_current + sum(usg_past[1:])

        update_curr_usg_col(acct_conn, usg_current, user, bank)
        update_hist_usg_col(acct_conn, usg_historical, user, bank)
    else:
        # found new jobs in the new half-life period

        # apply decay factor to past usage periods of a user's jobs
        usg_past = apply_decay_factor(0.5, acct_conn, user, bank)
        usg_historical = usg_current + usg_past

        update_curr_usg_col(acct_conn, usg_historical, user, bank)
        update_hist_usg_col(acct_conn, usg_historical, user, bank)

    return usg_historical


def check_end_hl(acct_conn, pdhl):
    hl_period = pdhl * 604800

    # fetch timestamp of the end of the current half-life period
    s_end_hl = """
        SELECT end_half_life_period
        FROM t_half_life_period_table
        WHERE cluster='cluster'
        """
    dataframe = pd.read_sql_query(s_end_hl, acct_conn)
    end_hl = dataframe.iloc[0]

    if float(end_hl) < (time.time() - hl_period):
        # update new end of half-life period timestamp
        update_timestamp_stmt = """
            UPDATE t_half_life_period_table
            SET end_half_life_period=?
            WHERE cluster='cluster'
            """
        acct_conn.execute(update_timestamp_stmt, ((float(end_hl) + hl_period),))
        acct_conn.commit()


def update_job_usage(acct_conn, jobs_conn, pdhl):
    s_assoc = "SELECT username, bank FROM association_table"
    dataframe = pd.read_sql_query(s_assoc, acct_conn)

    for _, row in dataframe.iterrows():
        calc_usage_factor(jobs_conn, acct_conn, pdhl, row["username"], row["bank"])

    check_end_hl(acct_conn, pdhl)
