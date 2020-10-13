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
import sqlite3
import time
import pwd
import csv

import pandas as pd


def count_ranks(ranks):
    if "-" in ranks:
        ranks_count = ranks.replace("-", ",").split(",")
        return int(ranks_count[1]) - int(ranks_count[0]) + 1
    else:
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
                    str(record.R),
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
    R_arr = []
    hostname_arr = []

    for record in job_records:
        userid_arr.append(record.userid)
        username_arr.append(record.username),
        jobid_arr.append(record.jobid),
        t_submit_arr.append(record.t_submit),
        t_run_arr.append(record.t_run),
        t_inactive_arr.append(record.t_inactive),
        nnodes_arr.append(record.nnodes),
        R_arr.append(record.R),

    records = {
        "UserID": userid_arr,
        "Username": username_arr,
        "JobID": jobid_arr,
        "T_Submit": t_submit_arr,
        "T_Run": t_run_arr,
        "T_Inactive": t_inactive_arr,
        "Nodes": nnodes_arr,
        "R": R_arr,
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


class JobRecord(object):
    """
    A record of an individual job.
    """

    def __init__(self, userid, username, jobid, t_submit, t_run, t_inactive, nnodes, R):
        self.userid = userid
        self.username = get_username(userid)
        self.jobid = jobid
        self.t_submit = t_submit
        self.t_run = t_run
        self.t_inactive = t_inactive
        self.nnodes = nnodes
        self.R = R
        return None

    @property
    def elapsed(self):
        return self.t_inactive - self.t_run

    @property
    def queued(self):
        return self.t_run - self.t_submit


def add_job_records(dataframe):
    job_records = []

    for index, row in dataframe.iterrows():
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
        key: val for (key, val) in kwargs.items() if val != None and key in valid_params
    }

    select_stmt = "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs "
    where_stmt = ""

    def append_to_where(where_stmt, conditional):
        if where_stmt != "":
            return "{} AND {} ".format(where_stmt, conditional)
        else:
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
    else:
        job_records = add_job_records(dataframe)
        if output_file is None:
            print_job_records(job_records)
        else:
            write_records_to_file(job_records, output_file)

    return job_records
