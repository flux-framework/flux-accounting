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
import argparse
import time
import sys
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
        return time.mktime(self.t_inactive) - time.mktime(self.t_run)

    @property
    def queued(self):
        return time.mktime(self.t_run) - time.mktime(self.t_submit)


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


def view_jobs_run_by_username(conn, username, output_file):
    # look up userid with username
    userid = get_uid(username)
    # get the information pertaining to a user in the jobs DB
    select_stmt = (
        "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs where userid=?"
    )
    dataframe = pd.read_sql_query(select_stmt, conn, params=(userid,))
    # if the length of dataframe is 0, that means
    # the user specified was not found in the table
    if len(dataframe.index) == 0:
        return "User not found in jobs table"
    else:
        job_records = add_job_records(dataframe)
        if output_file is None:
            print_job_records(job_records)
        else:
            write_records_to_file(job_records, output_file)

    return job_records


def view_jobs_with_jobid(conn, jobid, output_file):
    # get the information pertaining to a job in the jobs DB
    select_stmt = (
        "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs where id=?"
    )
    dataframe = pd.read_sql_query(select_stmt, conn, params=(jobid,))
    # if the length of dataframe is 0, that means
    # the jobid specified was not found in the table
    if len(dataframe.index) == 0:
        return "Job not found in jobs table"
    else:
        job_records = add_job_records(dataframe)
        if output_file is None:
            print_job_records(job_records)
        else:
            write_records_to_file(job_records, output_file)

    return job_records


def view_jobs_after_start_time(conn, time_after, output_file):
    # get jobs that have completed after a certain time
    select_stmt = (
        "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs WHERE t_run > ?"
    )
    dataframe = pd.read_sql_query(select_stmt, conn, params=(time_after,))
    # if the length of dataframe is 0, that means
    # the time specified resulted in no jobs found
    if len(dataframe.index) == 0:
        return "No jobs found after time specified"
    else:
        job_records = add_job_records(dataframe)
        if output_file is None:
            print_job_records(job_records)
        else:
            write_records_to_file(job_records, output_file)

    return job_records


def view_jobs_before_end_time(conn, time_before, output_file):
    # get jobs that have completed before a certain time
    select_stmt = "SELECT userid,id,t_submit,t_run,t_inactive,ranks,R FROM jobs WHERE t_inactive < ?"
    dataframe = pd.read_sql_query(select_stmt, conn, params=(time_before,))
    # if the length of dataframe is 0, that means
    # the time specified resulted in no jobs found
    if len(dataframe.index) == 0:
        return "No jobs found before time specified"
    else:
        job_records = add_job_records(dataframe)
        if output_file is None:
            print_job_records(job_records)
        else:
            write_records_to_file(job_records, output_file)

    return job_records


def add_bank(conn, bank, shares, parent_bank=""):
    # if the parent bank is not "", that means the account
    # trying to be added wants to be placed under a parent bank
    if parent_bank != "":
        try:
            select_stmt = "SELECT shares FROM bank_table where bank=?"
            dataframe = pd.read_sql_query(select_stmt, conn, params=(parent_bank,))
            # if length of dataframe is 0, that means the parent bank wasn't found
            if len(dataframe.index) == 0:
                raise Exception("Parent account not found in bank table")
        except pd.io.sql.DatabaseError as e_database_error:
            print(e_database_error)

    # insert the bank values into the database
    try:
        conn.execute(
            """
            INSERT INTO bank_table (
                bank,
                parent_bank,
                shares
            )
            VALUES (?, ?, ?)
            """,
            (bank, parent_bank, shares),
        )
        # commit changes
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def view_bank(conn, bank):
    try:
        # get the information pertaining to a bank in the Accounting DB
        select_stmt = "SELECT * FROM bank_table where bank=?"
        dataframe = pd.read_sql_query(select_stmt, conn, params=(bank,))
        # if the length of dataframe is 0, that means
        # the bank specified was not found in the table
        if len(dataframe.index) == 0:
            print("Bank not found in bank_table")
        else:
            print(dataframe)
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def delete_bank(conn, bank):
    last_parent_bank_seen = bank

    # delete bank from bank_table
    delete_stmt = "DELETE FROM bank_table WHERE bank=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (bank,))

    # commit changes
    conn.commit()


def edit_bank(conn, bank, shares):
    print(shares)
    # if user tries to edit a shares value <= 0,
    # raise an exception
    if shares <= 0:
        raise Exception("New shares amount must be >= 0")
    try:
        # edit value in bank_table
        conn.execute(
            "UPDATE bank_table SET shares=? WHERE bank=?", (shares, bank,),
        )
        # commit changes
        conn.commit()
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def print_hierarchy(conn):
    print("Bank = RawShares\n  | User = RawShares\n")
    select_stmt = """
        SELECT bank_table.bank,
        bank_table.shares,
        bank_table.parent_bank
        FROM bank_table;
        """
    dataframe = pd.read_sql_query(select_stmt, conn)
    for index, row in dataframe.iterrows():
        print("-" * 50)
        print(
            "Bank:",
            row["bank"],
            "| Shares =",
            row["shares"],
            "| Parent Bank:",
            row["parent_bank"],
        )
        print("-" * 50)
        select_stmt = """
            SELECT association_table.user_name,
            association_table.shares AS user_shares
            FROM association_table
            INNER JOIN bank_table ON association_table.account = ?;
            """
        dataframe = pd.read_sql_query(select_stmt, conn, params=(row["bank"],))
        users_seen = []
        for index, row in dataframe.iterrows():
            if row["user_name"] not in users_seen:
                print("  |", row["user_name"], "| Shares =", row["user_shares"])
                users_seen.append(row["user_name"])


def view_user(conn, user):
    try:
        # get the information pertaining to a user in the Accounting DB
        select_stmt = "SELECT * FROM association_table where user_name=?"
        dataframe = pd.read_sql_query(select_stmt, conn, params=(user,))
        # if the length of dataframe is 0, that means
        # the user specified was not found in the table
        if len(dataframe.index) == 0:
            print("User not found in association_table")
        else:
            print(dataframe)
    except pd.io.sql.DatabaseError as e_database_error:
        print(e_database_error)


def add_user(conn, username, admin_level, account, shares, max_jobs, max_wall_pj):

    # insert the user values into the database
    try:
        conn.execute(
            """
            INSERT INTO association_table (
                creation_time,
                mod_time,
                deleted,
                user_name,
                admin_level,
                account,
                shares,
                max_jobs,
                max_wall_pj
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                int(time.time()),
                0,
                username,
                admin_level,
                account,
                shares,
                max_jobs,
                max_wall_pj,
            ),
        )
        # commit changes
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def delete_user(conn, user):
    # delete user account from association_table
    delete_stmt = "DELETE FROM association_table WHERE user_name=?"
    cursor = conn.cursor()
    cursor.execute(delete_stmt, (user,))
    # commit changes
    conn.commit()


def edit_user(conn, username, field, new_value):
    fields = [
        "user_name",
        "admin_level",
        "account",
        "shares",
        "max_jobs",
        "max_wall_pj",
    ]
    if field in fields:
        the_field = field
    else:
        print("Field not found in association table")
        sys.exit(1)

    # edit value in accounting database
    conn.execute(
        "UPDATE association_table SET " + the_field + "=? WHERE user_name=?",
        (new_value, username,),
    )
    # commit changes
    conn.commit()
