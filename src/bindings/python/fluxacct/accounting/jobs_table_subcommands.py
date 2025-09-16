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
import json

from flux.resource import ResourceSet
from flux.job.JobID import JobID
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import util


class JobRecord:
    """
    A record of an individual job.
    """

    def __init__(
        self,
        userid,
        jobid,
        t_submit,
        t_run,
        t_inactive,
        nnodes,
        resources,
        project,
        bank,
        requested_duration,
        actual_duration,
    ):
        self.userid = userid
        self.username = util.get_username(userid)
        self.jobid = jobid
        self.t_submit = t_submit
        self.t_run = t_run
        self.t_inactive = t_inactive
        self.nnodes = nnodes
        self.resources = resources
        self.project = project
        self.bank = bank
        self.requested_duration = requested_duration
        self.actual_duration = actual_duration

    @property
    def elapsed(self):
        return self.t_inactive - self.t_run

    @property
    def queued(self):
        return self.t_run - self.t_submit

    @property
    def duration_delta(self):
        return self.requested_duration - self.actual_duration


def convert_to_str(job_records, fmt_string=None):
    """
    Convert the results of a query to the jobs table to a readable string
    that can either be output to stdout or written to a file.
    """
    # default format string
    if not fmt_string:
        fmt_string = (
            "{jobid:<15} | {username:<8} | {userid:<8} | {t_submit:<15.2f} | "
            + "{t_run:<15.2f} | {t_inactive:<15.2f} | {nnodes:<8} | {project:<8} | "
            + "{bank:<8} | {requested_duration:<18.2f} | {actual_duration:<15.2f} "
            + "{duration_delta:<18.2f}"
        )
    output = fmt.JobsFormatter(fmt_string)
    job_record_str = output.build_table(job_records)

    return job_record_str


def convert_to_obj(rows):
    """
    Convert the results of a query to the jobs table to a list of JobRecord
    objects.
    """
    job_records = []

    for row in rows:
        try:
            # attempt to create a ResourceSet from R
            rset = ResourceSet(row[6])
            job_nnodes = rset.nnodes
        except (ValueError, TypeError):
            # can't convert R to a ResourceSet object; skip it
            continue

        job_record = JobRecord(
            userid=row[0],
            jobid=row[1],
            t_submit=row[2],
            t_run=row[3],
            t_inactive=row[4],
            nnodes=job_nnodes,
            resources=row[6],
            project=row[8] if row[8] is not None else "",
            bank=row[9] if row[9] is not None else "",
            requested_duration=row[10],
            actual_duration=row[11],
        )
        job_records.append(job_record)

    return job_records


def check_jobspec(jobspec, bank):
    """
    Check if 1) a "bank" attribute exists in jobspec, which means the user
    submitted a job under a secondary bank, and 2) the "bank" attribute in
    jobspec matches the bank we are currently counting jobs for.
    """
    return bool(
        ("bank" in jobspec["attributes"]["system"])
        and (jobspec["attributes"]["system"]["bank"] == bank)
    )


def filter_jobs_by_bank(job_records, bank, is_default_bank=False):
    """
    Filter job records based on the specified bank. For a default bank, it
    includes jobs that either specify the default bank or do not specify any
    bank at all.
    """
    jobs = []
    for job in job_records:
        jobspec = json.loads(job[7])

        if check_jobspec(jobspec, bank):
            jobs.append(job)
        elif is_default_bank and "bank" not in jobspec["attributes"]["system"]:
            jobs.append(job)

    return jobs


def filter_jobs_by_association(conn, bank, default_bank, **kwargs):
    """
    Filter job records based on the specified association.
    """
    # fetch jobs under a specific userid
    result = get_jobs(conn, **kwargs)

    if not result:
        return []

    # find out if we are fetching jobs from an association's default bank or
    # under one of their secondary banks; this will determine how we further
    # filter the job records we've found based on the bank
    is_default_bank = bank == default_bank
    jobs = filter_jobs_by_bank(result, bank, is_default_bank)

    return convert_to_obj(jobs)


def validate_expressions(expressions):
    """
    Validate a list of passed-in expressions, such as "< 60", "> 120",
    or "= 90".

    Args:
        expressions: A list of expressions.
    """
    valid_expressions = []
    valid_operators = ["<=", "<", "=", ">=", ">"]
    operator = ""
    for expression in expressions:
        # split expression on spaces
        expression = expression.split(" ")
        if len(expression) != 2:
            raise ValueError("expression expects one operator and one value")
        if expression[0] not in valid_operators:
            raise ValueError("expression must start with <, <=, =, >=, or >")
        operator = expression[0]
        try:
            operand = float(expression[1])
        except ValueError:
            raise ValueError("expression expects to be compared with a number")
        valid_expressions.append((operator, operand))

    return valid_expressions


def get_jobs(conn, **kwargs):
    """
    A function to return jobs from the jobs table in the flux-accounting
    database. The query can be tuned to filter jobs by:

    - userid
    - jobs that started after a certain time
    - jobs that completed before a certain time
    - jobid
    - project
    - bank
    - requested duration
    - actual duration

    The function will execute a SQL query and return a list of jobs. If no
    jobs are found, an empty list is returned.
    """
    # find out which args were passed and place them in a dict
    valid_params = {
        "user",
        "after_start_time",
        "before_end_time",
        "jobid",
        "project",
        "bank",
        "requested_duration",
        "actual_duration",
        "duration_delta",
    }
    params = {
        key: val
        for key, val in kwargs.items()
        if val is not None and key in valid_params
    }

    select_stmt = (
        "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R,jobspec,project,bank,"
        "requested_duration,actual_duration FROM jobs"
    )
    where_clauses = []
    params_list = []

    if "user" in params:
        params["user"] = util.get_uid(params["user"])
        where_clauses.append("userid = ?")
        params_list.append(params["user"])
    if "after_start_time" in params:
        where_clauses.append("t_run > ?")
        params_list.append(util.parse_timestamp(params["after_start_time"]))
    if "before_end_time" in params:
        where_clauses.append("t_inactive < ?")
        params_list.append(util.parse_timestamp(params["before_end_time"]))
    if "jobid" in params:
        # convert jobID passed-in to decimal format
        params["jobid"] = JobID(params["jobid"]).dec
        where_clauses.append("id = ?")
        params_list.append(params["jobid"])
    if "project" in params:
        where_clauses.append("project = ?")
        params_list.append(params["project"])
    if "bank" in params:
        where_clauses.append("bank = ?")
        params_list.append(params["bank"])
    if "requested_duration" in params:
        # validate one or multiple expressions
        expressions = validate_expressions(params["requested_duration"])
        for expression in expressions:
            where_clauses.append(f"requested_duration {expression[0]} ?")
            params_list.append(expression[1])
    if "actual_duration" in params:
        # validate one or multiple expressions
        expressions = validate_expressions(params["actual_duration"])
        for expression in expressions:
            where_clauses.append(f"actual_duration {expression[0]} ?")
            params_list.append(expression[1])
    if "duration_delta" in params:
        expressions = validate_expressions(params["duration_delta"])
        for expression in expressions:
            where_clauses.append(
                f"requested_duration - actual_duration {expression[0]} ?"
            )
            params_list.append(expression[1])

    if where_clauses:
        select_stmt += " WHERE " + " AND ".join(where_clauses)

    cur = conn.cursor()
    cur.execute(select_stmt, tuple(params_list))
    job_records = cur.fetchall()

    return job_records


def view_jobs(conn, fields, **kwargs):
    # look up jobs in jobs table
    job_records = convert_to_obj(get_jobs(conn, **kwargs))
    # convert query result to a readable string
    job_records_str = convert_to_str(job_records, fields)

    return job_records_str
