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
import sys
import os

import fluxacct.accounting
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import job_archive_interface as jobs
from fluxacct.accounting import create_db as c
from fluxacct.accounting import queue_subcommands as qu


def add_path_arg(parser):
    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )


def add_output_file_arg(parser):
    parser.add_argument(
        "-o",
        "--output-file",
        dest="output_file",
        help="specify location of output file",
    )


def add_view_user_arg(subparsers):
    subparser_view_user = subparsers.add_parser(
        "view-user", help="view a user's information in the accounting database"
    )
    subparser_view_user.set_defaults(func="view_user")
    subparser_view_user.add_argument("username", help="username", metavar=("USERNAME"))


def add_add_user_arg(subparsers):
    subparser_add_user = subparsers.add_parser(
        "add-user", help="add a user to the accounting database"
    )
    subparser_add_user.set_defaults(func="add_user")
    subparser_add_user.add_argument(
        "--username",
        help="username",
        metavar="USERNAME",
    )
    subparser_add_user.add_argument(
        "--userid",
        help="userid",
        default=65534,
        metavar="USERID",
    )
    subparser_add_user.add_argument(
        "--bank",
        help="bank to charge jobs against",
        metavar="BANK",
    )
    subparser_add_user.add_argument(
        "--shares",
        help="shares",
        default=1,
        metavar="SHARES",
    )
    subparser_add_user.add_argument(
        "--max-running-jobs",
        help="max number of jobs that can be running at the same time",
        default=5,
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_add_user.add_argument(
        "--max-active-jobs",
        help="max number of both pending and running jobs",
        default=7,
        metavar="max_active_jobs",
    )
    subparser_add_user.add_argument(
        "--max-nodes",
        help="max number of nodes a user can have across all of their running jobs",
        default=2147483647,
        metavar="MAX_NODES",
    )
    subparser_add_user.add_argument(
        "--queues",
        help="queues the user is allowed to run jobs in",
        default="",
        metavar="QUEUES",
    )
    subparser_add_user.add_argument(
        "--projects",
        help="projects the user is allowed to submit jobs under",
        default="*",
        metavar="PROJECTS",
    )


def add_delete_user_arg(subparsers):
    subparser_delete_user = subparsers.add_parser(
        "delete-user", help="remove a user from the accounting database"
    )
    subparser_delete_user.set_defaults(func="delete_user")
    subparser_delete_user.add_argument(
        "username", help="username", metavar=("USERNAME")
    )
    subparser_delete_user.add_argument("bank", help="bank", metavar=("BANK"))


def add_edit_user_arg(subparsers):
    subparser_edit_user = subparsers.add_parser("edit-user", help="edit a user's value")
    subparser_edit_user.set_defaults(func="edit_user")
    subparser_edit_user.add_argument(
        "username",
        help="username",
        metavar="USERNAME",
    )
    subparser_edit_user.add_argument(
        "--bank",
        help="bank to charge jobs against",
        default=None,
        metavar="BANK",
    )
    subparser_edit_user.add_argument(
        "--default-bank",
        help="default bank",
        default=None,
        metavar="DEFAULT_BANK",
    )
    subparser_edit_user.add_argument(
        "--shares",
        help="shares",
        default=None,
        metavar="SHARES",
    )
    subparser_edit_user.add_argument(
        "--max-running-jobs",
        help="max number of jobs that can be running at the same time",
        default=None,
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_edit_user.add_argument(
        "--max-active-jobs",
        help="max number of both pending and running jobs",
        default=7,
        metavar="max_active_jobs",
    )
    subparser_edit_user.add_argument(
        "--max-nodes",
        help="max number of nodes a user can have across all of their running jobs",
        default=5,
        metavar="MAX_NODES",
    )
    subparser_edit_user.add_argument(
        "--queues",
        help="queues the user is allowed to run jobs in",
        default=None,
        metavar="QUEUES",
    )
    subparser_edit_user.add_argument(
        "--projects",
        help="projects the user is allowed to submit jobs under",
        default=None,
        metavar="PROJECTS",
    )
    subparser_edit_user.add_argument(
        "--default-project",
        help="default projects the user submits jobs under when no project is specified",
        default=None,
        metavar="DEFAULT_PROJECT",
    )


def add_view_job_records_arg(subparsers):
    subparser_view_job_records = subparsers.add_parser(
        "view-job-records", help="view job records"
    )
    subparser_view_job_records.set_defaults(func="view_job_records")
    subparser_view_job_records.add_argument(
        "-u",
        "--user",
        help="username",
        metavar="USERNAME",
    )
    subparser_view_job_records.add_argument(
        "-j", "--jobid", help="jobid", metavar="JOBID"
    )
    subparser_view_job_records.add_argument(
        "-a",
        "--after-start-time",
        help="start time",
        metavar="START TIME",
    )
    subparser_view_job_records.add_argument(
        "-b",
        "--before-end-time",
        help="end time",
        metavar="END TIME",
    )


def add_create_db_arg(subparsers):
    subparser_create_db = subparsers.add_parser(
        "create-db", help="create the flux-accounting database"
    )
    subparser_create_db.set_defaults(func="create_db")
    subparser_create_db.add_argument(
        "--priority-usage-reset-period",
        help="the number of weeks at which usage information gets reset to 0",
        metavar=("PRIORITY USAGE RESET PERIOD"),
    )
    subparser_create_db.add_argument(
        "--priority-decay-half-life",
        help="contribution of historical usage in weeks on the composite usage value",
        metavar=("PRIORITY DECAY HALF LIFE"),
    )


def add_add_bank_arg(subparsers):
    subparser_add_bank = subparsers.add_parser("add-bank", help="add a new bank")
    subparser_add_bank.set_defaults(func="add_bank")
    subparser_add_bank.add_argument(
        "bank",
        help="bank name",
        metavar="BANK",
    )
    subparser_add_bank.add_argument(
        "--parent-bank", help="parent bank name", default="", metavar="PARENT BANK"
    )
    subparser_add_bank.add_argument(
        "shares", help="number of shares to allocate to bank", metavar="SHARES"
    )


def add_view_bank_arg(subparsers):
    subparser_view_bank = subparsers.add_parser(
        "view-bank", help="view bank information"
    )
    subparser_view_bank.set_defaults(func="view_bank")
    subparser_view_bank.add_argument(
        "bank",
        help="bank name",
        metavar="BANK",
    )
    subparser_view_bank.add_argument(
        "-t",
        "--tree",
        action="store_const",
        const=True,
        help="list all sub banks in a tree format with specified bank as root of tree",
        metavar="TREE",
    )
    subparser_view_bank.add_argument(
        "-u",
        "--users",
        action="store_const",
        const=True,
        help="list all potential users under bank",
        metavar="USERS",
    )


def add_delete_bank_arg(subparsers):
    subparser_delete_bank = subparsers.add_parser("delete-bank", help="remove a bank")
    subparser_delete_bank.set_defaults(func="delete_bank")
    subparser_delete_bank.add_argument(
        "bank",
        help="bank name",
        metavar="BANK",
    )


def add_edit_bank_arg(subparsers):
    subparser_edit_bank = subparsers.add_parser(
        "edit-bank", help="edit a bank's allocation"
    )
    subparser_edit_bank.set_defaults(func="edit_bank")
    subparser_edit_bank.add_argument(
        "bank",
        help="bank",
        metavar="BANK",
    )
    subparser_edit_bank.add_argument(
        "--shares",
        help="new shares value",
        metavar="SHARES",
    )


def add_update_usage_arg(subparsers):
    subparser_update_usage = subparsers.add_parser(
        "update-usage", help="update usage factors for associations"
    )
    subparser_update_usage.set_defaults(func="update_usage")
    subparser_update_usage.add_argument(
        "job_archive_db_path",
        help="job-archive DB location",
        metavar="JOB-ARCHIVE_DB_PATH",
    )
    subparser_update_usage.add_argument(
        "--priority-decay-half-life",
        default=1,
        type=int,
        help="number of weeks for a job's usage contribution to a half-life decay",
        metavar="PRIORITY DECAY HALF LIFE",
    )


def add_add_queue_arg(subparsers):
    subparser_add_queue = subparsers.add_parser("add-queue", help="add a new queue")

    subparser_add_queue.set_defaults(func="add_queue")
    subparser_add_queue.add_argument("queue", help="queue name", metavar="QUEUE")
    subparser_add_queue.add_argument(
        "--min-nodes-per-job",
        help="min nodes per job",
        default=1,
        metavar="MIN NODES PER JOB",
    )
    subparser_add_queue.add_argument(
        "--max-nodes-per-job",
        help="max nodes per job",
        default=1,
        metavar="MAX NODES PER JOB",
    )
    subparser_add_queue.add_argument(
        "--max-time-per-job",
        help="max time per job",
        default=60,
        metavar="MAX TIME PER JOB",
    )
    subparser_add_queue.add_argument(
        "--priority",
        help="associated priority for the queue",
        default=0,
        metavar="PRIORITY",
    )


def add_view_queue_arg(subparsers):
    subparser_view_queue = subparsers.add_parser(
        "view-queue", help="view queue information"
    )

    subparser_view_queue.set_defaults(func="view_queue")
    subparser_view_queue.add_argument("queue", help="queue name", metavar="QUEUE")


def add_edit_queue_arg(subparsers):
    subparser_edit_queue = subparsers.add_parser(
        "edit-queue", help="edit a queue's priority"
    )

    subparser_edit_queue.set_defaults(func="edit_queue")
    subparser_edit_queue.add_argument("queue", help="queue name", metavar="QUEUE")
    subparser_edit_queue.add_argument(
        "--min-nodes-per-job",
        help="min nodes per job",
        default=None,
        metavar="MIN NODES PER JOB",
    )
    subparser_edit_queue.add_argument(
        "--max-nodes-per-job",
        help="max nodes per job",
        default=None,
        metavar="MAX NODES PER JOB",
    )
    subparser_edit_queue.add_argument(
        "--max-time-per-job",
        help="max time per job",
        default=None,
        metavar="MAX TIME PER JOB",
    )
    subparser_edit_queue.add_argument(
        "--priority",
        help="associated priority for the queue",
        default=None,
        metavar="PRIORITY",
    )


def add_delete_queue_arg(subparsers):
    subparser_delete_queue = subparsers.add_parser(
        "delete-queue", help="remove a queue"
    )

    subparser_delete_queue.set_defaults(func="delete_queue")
    subparser_delete_queue.add_argument("queue", help="queue name", metavar="QUEUE")


def add_arguments_to_parser(parser, subparsers):
    add_path_arg(parser)
    add_output_file_arg(parser)
    add_view_user_arg(subparsers)
    add_add_user_arg(subparsers)
    add_delete_user_arg(subparsers)
    add_edit_user_arg(subparsers)
    add_view_job_records_arg(subparsers)
    add_create_db_arg(subparsers)
    add_add_bank_arg(subparsers)
    add_view_bank_arg(subparsers)
    add_delete_bank_arg(subparsers)
    add_edit_bank_arg(subparsers)
    add_update_usage_arg(subparsers)
    add_add_queue_arg(subparsers)
    add_view_queue_arg(subparsers)
    add_edit_queue_arg(subparsers)
    add_delete_queue_arg(subparsers)


def set_db_location(args):
    path = args.path if args.path else fluxacct.accounting.db_path

    return path


def establish_sqlite_connection(path):
    # try to open database file; will exit with -1 if database file not found
    if not os.path.isfile(path):
        print(f"Database file does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        # set foreign keys constraint
        conn.execute("PRAGMA foreign_keys = 1")
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(1)

    return conn


def set_output_file(args):
    # set path for output file
    output_file = args.output_file if args.output_file else None

    return output_file


def select_accounting_function(args, conn, output_file, parser):
    if args.func == "view_user":
        u.view_user(conn, args.username)
    elif args.func == "add_user":
        u.add_user(
            conn,
            args.username,
            args.bank,
            args.userid,
            args.shares,
            args.max_running_jobs,
            args.max_active_jobs,
            args.max_nodes,
            args.queues,
            args.projects,
        )
    elif args.func == "delete_user":
        u.delete_user(conn, args.username, args.bank)
    elif args.func == "edit_user":
        u.edit_user(
            conn,
            args.username,
            args.bank,
            args.default_bank,
            args.shares,
            args.max_running_jobs,
            args.max_active_jobs,
            args.max_nodes,
            args.queues,
            args.projects,
            args.default_project,
        )
    elif args.func == "view_job_records":
        jobs.output_job_records(
            conn,
            output_file,
            jobid=args.jobid,
            user=args.user,
            before_end_time=args.before_end_time,
            after_start_time=args.after_start_time,
        )
    elif args.func == "add_bank":
        b.add_bank(conn, args.bank, args.shares, args.parent_bank)
    elif args.func == "view_bank":
        b.view_bank(conn, args.bank, args.tree, args.users)
    elif args.func == "delete_bank":
        b.delete_bank(conn, args.bank)
    elif args.func == "edit_bank":
        b.edit_bank(conn, args.bank, args.shares)
    elif args.func == "update_usage":
        jobs_conn = establish_sqlite_connection(args.job_archive_db_path)
        jobs.update_job_usage(conn, jobs_conn, args.priority_decay_half_life)
    elif args.func == "add_queue":
        qu.add_queue(
            conn,
            args.queue,
            args.min_nodes_per_job,
            args.max_nodes_per_job,
            args.max_time_per_job,
            args.priority,
        )
    elif args.func == "view_queue":
        qu.view_queue(conn, args.queue)
    elif args.func == "delete_queue":
        qu.delete_queue(conn, args.queue)
    elif args.func == "edit_queue":
        qu.edit_queue(
            conn,
            args.queue,
            args.min_nodes_per_job,
            args.max_nodes_per_job,
            args.max_time_per_job,
            args.priority,
        )
    else:
        print(parser.print_usage())


def main():

    parser = argparse.ArgumentParser(
        description="""
        Description: Translate command line arguments into
        SQLite instructions for the Flux Accounting Database.
        """
    )
    subparsers = parser.add_subparsers(help="sub-command help", dest="subcommand")
    subparsers.required = True

    add_arguments_to_parser(parser, subparsers)
    args = parser.parse_args()

    path = set_db_location(args)

    # if we are creating the DB for the first time, we need
    # to ONLY create the DB and then exit out successfully
    if args.func == "create_db":
        c.create_db(
            path, args.priority_usage_reset_period, args.priority_decay_half_life
        )
        sys.exit(0)

    conn = establish_sqlite_connection(path)

    output_file = set_output_file(args)

    try:
        select_accounting_function(args, conn, output_file, parser)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
