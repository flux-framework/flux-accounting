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
import pwd
import csv
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


def add_job_records(rows):
    job_records = []

    for row in rows:
        try:
            # attempt to create a ResourceSet from R
            rset = ResourceSet(row[6])
            nnodes = rset.nnodes
        except (ValueError, TypeError):
            # can't convert R to a ResourceSet object; skip it
            continue

        job_record = JobRecord(
            row[0],  # userid
            get_username(row[0]),  # username
            row[1],  # jobid
            row[2],  # t_submit
            row[3],  # t_run
            row[4],  # t_inactive
            nnodes,  # nnodes
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


# Filter job records based on the specified bank. For a default bank,
# it includes jobs that either specify the default bank or do not
# specify any bank at all.
def filter_jobs_by_bank(job_records, bank, is_default_bank=False):
    jobs = []
    for job in job_records:
        jobspec = json.loads(job[7])

        if check_jobspec(jobspec, bank):
            jobs.append(job)
        elif is_default_bank and "bank" not in jobspec["attributes"]["system"]:
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

    # find out if we are fetching jobs from a user's default bank or under
    # one of their secondary banks; this will determine how we filter the
    # job records we've found
    is_default_bank = bank == default_bank
    jobs = filter_jobs_by_bank(result, bank, is_default_bank)

    return add_job_records(jobs)


def output_job_records(conn, output_file, **kwargs):
    job_record_str = ""
    job_records = get_job_records(conn, None, None, **kwargs)

    job_record_str = fetch_job_records(job_records)

    if output_file is None:
        return job_record_str

    write_records_to_file(job_records, output_file)

    return job_record_str
