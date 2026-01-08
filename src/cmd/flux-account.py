###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import argparse
import sys
import logging
import subprocess

import flux
from flux.constants import FLUX_USERID_UNKNOWN
import fluxacct.accounting

from fluxacct.accounting import create_db as c


def add_path_arg(parser):
    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )


def add_view_user_arg(subparsers):
    subparser_view_user = subparsers.add_parser(
        "view-user",
        help="view a user's information in the accounting database",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_view_user.set_defaults(func="view_user")
    subparser_view_user.add_argument("username", help="username", metavar=("USERNAME"))
    subparser_view_user.add_argument(
        "--parsable",
        action="store_const",
        const=True,
        help="print all information of an association on one line",
        metavar="PARSABLE",
    )
    subparser_view_user.add_argument(
        "--list-banks",
        action="store_const",
        const=True,
        help="list all of the banks a user belongs to",
        metavar="LIST_BANKS",
    )
    subparser_view_user.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )
    group = subparser_view_user.add_mutually_exclusive_group()
    group.add_argument(
        "--fields",
        type=str,
        help="list of fields to include in JSON output",
        default=None,
        metavar=(
            "CREATION_TIME,MOD_TIME,ACTIVE,USERNAME,USERID,BANK,DEFAULT_BANK,"
            "SHARES,JOB_USAGE,FAIRSHARE,MAX_RUNNING_JOBS,MAX_ACTIVE_JOBS,MAX_NODES,"
            "MAX_CORES,QUEUES,PROJECTS,DEFAULT_PROJECT,MAX_SCHED_JOBS"
        ),
    )
    group.add_argument(
        "-J",
        "--job-usage",
        action="store_const",
        const=True,
        help="display breakdown of an association's historical job usage",
    )


def add_list_users_arg(subparsers):
    subparser_list_users = subparsers.add_parser(
        "list-users",
        help="list all associations in association_table",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_list_users.set_defaults(func="list_users")
    subparser_list_users.add_argument(
        "-f",
        "--fields",
        type=str,
        help="list of fields to include in output",
        default=None,
        metavar=f"{','.join(fluxacct.accounting.ASSOCIATION_TABLE)}",
    )
    subparser_list_users.add_argument(
        "-j",
        "--json",
        action="store_const",
        const=True,
        help="print output in JSON format",
    )
    subparser_list_users.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )
    subparser_list_users.add_argument(
        "--active",
        metavar="ACTIVE_STATUS",
    )
    subparser_list_users.add_argument(
        "-B",
        "--bank",
        metavar="BANK",
    )
    subparser_list_users.add_argument(
        "--shares",
        metavar="SHARES",
    )
    subparser_list_users.add_argument(
        "--max-running-jobs",
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_list_users.add_argument(
        "--max-active-jobs",
        metavar="MAX_ACTIVE_JOBS",
    )
    subparser_list_users.add_argument(
        "-N",
        "--max-nodes",
        metavar="MAX_NODES",
    )
    subparser_list_users.add_argument(
        "-c",
        "--max-cores",
        metavar="MAX_CORES",
    )
    subparser_list_users.add_argument(
        "-q",
        "--queues",
        metavar="QUEUES",
    )
    subparser_list_users.add_argument(
        "-P",
        "--projects",
        metavar="PROJECTS",
    )
    subparser_list_users.add_argument(
        "--default-project",
        metavar="DEFAULT_PROJECT",
    )
    subparser_list_users.add_argument(
        "--max-sched-jobs",
        metavar="MAX_SCHED_JOBS",
    )


def add_add_user_arg(subparsers):
    subparser_add_user = subparsers.add_parser(
        "add-user",
        help="add a user to the accounting database",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_add_user.set_defaults(func="add_user")
    subparser_add_user.add_argument(
        "-u",
        "--username",
        help="username",
        metavar="USERNAME",
        required=True,
    )
    subparser_add_user.add_argument(
        "-i",
        "--userid",
        help="userid",
        default=FLUX_USERID_UNKNOWN,
        metavar="USERID",
    )
    subparser_add_user.add_argument(
        "-B",
        "--bank",
        help="bank to charge jobs against",
        metavar="BANK",
        required=True,
    )
    subparser_add_user.add_argument(
        "--shares",
        help="shares",
        default=1,
        metavar="SHARES",
    )
    subparser_add_user.add_argument(
        "--fairshare",
        help="fairshare",
        type=float,
        default=0.5,
        metavar="FAIRSHARE",
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
        "-N",
        "--max-nodes",
        help="max number of nodes a user can have across all of their running jobs",
        default=2147483647,
        metavar="MAX_NODES",
    )
    subparser_add_user.add_argument(
        "-c",
        "--max-cores",
        help="max number of cores a user can have across all of their running jobs",
        default=2147483647,
        metavar="MAX_CORES",
    )
    subparser_add_user.add_argument(
        "-q",
        "--queues",
        help="queues the user is allowed to run jobs in",
        default="",
        metavar="QUEUES",
    )
    subparser_add_user.add_argument(
        "-P",
        "--projects",
        help="projects the user is allowed to submit jobs under",
        default="*",
        metavar="PROJECTS",
    )
    subparser_add_user.add_argument(
        "--default-project",
        help="the default project for the association to submit jobs under",
        default=None,
        metavar="DEFAULT_PROJECT",
    )
    subparser_add_user.add_argument(
        "--max-sched-jobs",
        help="max number of jobs in SCHED state the user can have at any given time",
        default=2147483647,
        metavar="NJOBS",
    )


def add_delete_user_arg(subparsers):
    subparser_delete_user = subparsers.add_parser(
        "delete-user",
        help="remove a user from the accounting database",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_delete_user.set_defaults(func="delete_user")
    subparser_delete_user.add_argument(
        "username", help="username", metavar=("USERNAME")
    )
    subparser_delete_user.add_argument("bank", help="bank", metavar=("BANK"))
    subparser_delete_user.add_argument(
        "--force",
        action="store_const",
        const=True,
        default=False,
        help=(
            "actually remove user from association_table (WARNING: removing a row from "
            "the association_table can affect a bank and its users' fair-share value; "
            "proceed with caution)"
        ),
    )


def add_edit_user_arg(subparsers):
    subparser_edit_user = subparsers.add_parser(
        "edit-user",
        help="edit a user's value",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_edit_user.set_defaults(func="edit_user")
    subparser_edit_user.add_argument(
        "username",
        help="username",
        metavar="USERNAME",
    )
    subparser_edit_user.add_argument(
        "-B",
        "--bank",
        help=(
            "specify under which bank to make this change; if not specified,"
            " the edit will be applied across all of the user's accounts"
        ),
        default=None,
        metavar="BANK",
    )
    subparser_edit_user.add_argument(
        "-i",
        "--userid",
        default=None,
        metavar="USERID",
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
        "--fairshare",
        help="fairshare",
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
        default=None,
        metavar="max_active_jobs",
    )
    subparser_edit_user.add_argument(
        "-N",
        "--max-nodes",
        help="max number of nodes a user can have across all of their running jobs",
        default=None,
        metavar="MAX_NODES",
    )
    subparser_edit_user.add_argument(
        "-c",
        "--max-cores",
        help="max number of cores a user can have across all of their running jobs",
        default=None,
        metavar="MAX_CORES",
    )
    subparser_edit_user.add_argument(
        "-q",
        "--queues",
        help="queues the user is allowed to run jobs in",
        default=None,
        metavar="QUEUES",
    )
    subparser_edit_user.add_argument(
        "-P",
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
    subparser_edit_user.add_argument(
        "--max-sched-jobs",
        help="max number of jobs in SCHED state the user can have at any given time",
        default=None,
        metavar="NJOBS",
    )


def add_edit_all_users_arg(subparsers):
    subparser_edit_all_users = subparsers.add_parser(
        "edit-all-users",
        help="edit an attribute for every row in association_table",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_edit_all_users.set_defaults(func="edit_all_users")
    subparser_edit_all_users.add_argument(
        "--bank",
        help="bank to charge jobs against",
        default=None,
        metavar="BANK",
    )
    subparser_edit_all_users.add_argument(
        "--default-bank",
        help="default bank",
        default=None,
        metavar="DEFAULT_BANK",
    )
    subparser_edit_all_users.add_argument(
        "--shares",
        help="shares",
        default=None,
        metavar="SHARES",
    )
    subparser_edit_all_users.add_argument(
        "--fairshare",
        help="fairshare",
        default=None,
        metavar="SHARES",
    )
    subparser_edit_all_users.add_argument(
        "--max-running-jobs",
        help="max number of jobs that can be running at the same time",
        default=None,
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_edit_all_users.add_argument(
        "--max-active-jobs",
        help="max number of both pending and running jobs",
        default=None,
        metavar="max_active_jobs",
    )
    subparser_edit_all_users.add_argument(
        "--max-nodes",
        help="max number of nodes all users can have across all of their running jobs",
        default=None,
        metavar="MAX_NODES",
    )
    subparser_edit_all_users.add_argument(
        "--max-cores",
        help="max number of cores all users can have across all of their running jobs",
        default=None,
        metavar="MAX_CORES",
    )
    subparser_edit_all_users.add_argument(
        "--queues",
        help="queues the users are allowed to run jobs in",
        default=None,
        metavar="QUEUES",
    )
    subparser_edit_all_users.add_argument(
        "--projects",
        help="projects the users are allowed to submit jobs under",
        default=None,
        metavar="PROJECTS",
    )
    subparser_edit_all_users.add_argument(
        "--default-project",
        help=(
            "the default project the users submit jobs under when no project is "
            "specified"
        ),
        default=None,
        metavar="DEFAULT_PROJECT",
    )
    subparser_edit_all_users.add_argument(
        "--max-sched-jobs",
        help="max number of jobs in SCHED state the user can have at any given time",
        default=None,
        metavar="NJOBS",
    )


def add_view_job_records_arg(subparsers):
    subparser_view_job_records = subparsers.add_parser(
        "view-job-records",
        help="view job records",
        formatter_class=flux.util.help_formatter(),
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
        help=(
            "start time; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        metavar="START TIME",
    )
    subparser_view_job_records.add_argument(
        "-b",
        "--before-end-time",
        help=(
            "end time; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        metavar="END TIME",
    )
    subparser_view_job_records.add_argument(
        "--project",
        help="project",
        metavar="PROJECT",
    )
    subparser_view_job_records.add_argument(
        "-B",
        "--bank",
        help="bank",
        metavar="BANK",
    )
    subparser_view_job_records.add_argument(
        "-d",
        "--requested-duration",
        nargs="+",
        help=(
            "the requested duration for a job; multiple expressions can be passed as "
            "filters, e.g. -d '< 60' '> 120'"
        ),
        metavar="[EXPRESSIONS]",
    )
    subparser_view_job_records.add_argument(
        "-e",
        "--actual-duration",
        nargs="+",
        help=(
            "the actual duration for a job; multiple expressions can be passed as "
            "filters, e.g. -e '< 60' '> 120'"
        ),
        metavar="[EXPRESSIONS]",
    )
    subparser_view_job_records.add_argument(
        "-D",
        "--duration-delta",
        nargs="+",
        help=(
            "the difference between the requested duration of a job and its actual "
            "duration; multiple expressions can be passed as filters, e.g. -D '< 60' "
            "'> 120'"
        ),
        metavar="[EXPRESSIONS]",
    )
    subparser_view_job_records.add_argument(
        "-o",
        "--format",
        type=str,
        help=(
            "Specify output format using Python's string format syntax. "
            "Available fields: jobid,username,userid,t_submit,t_run,t_inactive,nnodes,"
            "project,bank"
        ),
        metavar="FORMAT",
    )


def add_create_db_arg(subparsers):
    subparser_create_db = subparsers.add_parser(
        "create-db",
        help="create the flux-accounting database",
        formatter_class=flux.util.help_formatter(),
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
    subparser_add_bank = subparsers.add_parser(
        "add-bank", help="add a new bank", formatter_class=flux.util.help_formatter()
    )
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
    subparser_add_bank.add_argument(
        "--priority",
        type=float,
        default=0.0,
        help="an associated priority for jobs submitted under this bank",
        metavar="PRIORITY",
    )
    subparser_add_bank.add_argument(
        "--ignore-older-than",
        help=(
            "a timestamp to which older jobs will be ignored when calculating job "
            "usage; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        default=0,
        metavar="TIMESTAMP",
    )


def add_view_bank_arg(subparsers):
    subparser_view_bank = subparsers.add_parser(
        "view-bank",
        help="view bank information",
        formatter_class=flux.util.help_formatter(),
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
    subparser_view_bank.add_argument(
        "-P",
        "--parsable",
        action="store_const",
        const=True,
        help="list all sub banks in a parsable format with specified bank as root of tree",
        metavar="PARSABLE",
    )
    subparser_view_bank.add_argument(
        "--fields",
        type=str,
        help="list of fields to include in JSON output",
        default=None,
        metavar="BANK_ID,BANK,ACTIVE,PARENT_BANK,SHARES,JOB_USAGE",
    )
    subparser_view_bank.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )
    subparser_view_bank.add_argument(
        "-c",
        "--concise",
        action="store_const",
        const=True,
        help="only list associations that have a job usage value > 0",
    )


def add_delete_bank_arg(subparsers):
    subparser_delete_bank = subparsers.add_parser(
        "delete-bank", help="remove a bank", formatter_class=flux.util.help_formatter()
    )
    subparser_delete_bank.set_defaults(func="delete_bank")
    subparser_delete_bank.add_argument(
        "bank",
        help="bank name",
        metavar="BANK",
    )
    subparser_delete_bank.add_argument(
        "--force",
        action="store_const",
        const=True,
        default=False,
        help=(
            "actually remove bank from bank_table (WARNING: removing a row from "
            "the bank_table can affect a bank and its users' fair-share value; "
            "proceed with caution)"
        ),
    )


def add_edit_bank_arg(subparsers):
    subparser_edit_bank = subparsers.add_parser(
        "edit-bank",
        help="edit a bank's allocation",
        formatter_class=flux.util.help_formatter(),
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
    subparser_edit_bank.add_argument(
        "--parent-bank",
        help="parent bank",
        metavar="PARENT BANK",
    )
    subparser_edit_bank.add_argument(
        "--priority",
        help="an associated priority for jobs submitted under this bank",
        metavar="PRIORITY",
    )
    subparser_edit_bank.add_argument(
        "--ignore-older-than",
        help=(
            "a timestamp to which older jobs will be ignored when calculating job "
            "usage; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        default=None,
        metavar="TIMESTAMP",
    )


def add_list_banks_arg(subparsers):
    subparser_list_banks = subparsers.add_parser(
        "list-banks",
        help="list all banks in the flux-accounting DB",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_list_banks.set_defaults(func="list_banks")
    subparser_list_banks.add_argument(
        "--inactive",
        action="store_const",
        const=True,
        help="include inactive banks in output",
    )
    subparser_list_banks.add_argument(
        "--fields",
        type=str,
        help="list of fields to include in JSON output",
        default=None,
        metavar="BANK_ID,BANK,ACTIVE,PARENT_BANK,SHARES,JOB_USAGE",
    )
    subparser_list_banks.add_argument(
        "--json",
        action="store_const",
        const=True,
        help="print output in JSON format",
    )
    subparser_list_banks.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )


def add_update_usage_arg(subparsers):
    subparser_update_usage = subparsers.add_parser(
        "update-usage",
        help="update usage factors for associations",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_update_usage.set_defaults(func="update_usage")
    subparser_update_usage.add_argument(
        "--priority-decay-half-life",
        default=1,
        type=int,
        help="number of weeks for a job's usage contribution to a half-life decay",
        metavar="PRIORITY DECAY HALF LIFE",
    )


def add_add_queue_arg(subparsers):
    subparser_add_queue = subparsers.add_parser(
        "add-queue", help="add a new queue", formatter_class=flux.util.help_formatter()
    )

    subparser_add_queue.set_defaults(func="add_queue")
    subparser_add_queue.add_argument("queue", help="queue name", metavar="QUEUE")
    subparser_add_queue.add_argument(
        "--min-nodes-per-job",
        help="min nodes per job",
        default=1,
        metavar="MIN NODES PER JOB",
    )
    subparser_add_queue.add_argument(
        "-N",
        "--max-nodes-per-job",
        help="max nodes per job",
        default=1,
        metavar="MAX NODES PER JOB",
    )
    subparser_add_queue.add_argument(
        "-t",
        "--max-time-per-job",
        help="max time per job",
        default=60,
        metavar="MAX TIME PER JOB",
    )
    subparser_add_queue.add_argument(
        "-P",
        "--priority",
        help="associated priority for the queue",
        default=0,
        metavar="PRIORITY",
    )
    subparser_add_queue.add_argument(
        "--max-running-jobs",
        help="max number of running jobs an association can have in the queue",
        default=100,
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_add_queue.add_argument(
        "--max-nodes-per-assoc",
        help=(
            "max number of nodes an association can have across all of their running "
            "jobs in the queue"
        ),
        default=2147483647,
        metavar="MAX_NODES_PER_ASSOC",
    )


def add_view_queue_arg(subparsers):
    subparser_view_queue = subparsers.add_parser(
        "view-queue",
        help="view queue information",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_view_queue.set_defaults(func="view_queue")
    subparser_view_queue.add_argument("queue", help="queue name", metavar="QUEUE")
    subparser_view_queue.add_argument(
        "--parsable",
        action="store_const",
        const=True,
        help="print all information about a queue on one line",
        metavar="PARSABLE",
    )
    subparser_view_queue.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )


def add_edit_queue_arg(subparsers):
    subparser_edit_queue = subparsers.add_parser(
        "edit-queue",
        help="edit a queue's priority",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_edit_queue.set_defaults(func="edit_queue")
    subparser_edit_queue.add_argument("queue", help="queue name", metavar="QUEUE")
    subparser_edit_queue.add_argument(
        "--min-nodes-per-job",
        type=int,
        help="min nodes per job",
        default=None,
        metavar="MIN NODES PER JOB",
    )
    subparser_edit_queue.add_argument(
        "-N",
        "--max-nodes-per-job",
        type=int,
        help="max nodes per job",
        default=None,
        metavar="MAX NODES PER JOB",
    )
    subparser_edit_queue.add_argument(
        "-t",
        "--max-time-per-job",
        type=int,
        help="max time per job",
        default=None,
        metavar="MAX TIME PER JOB",
    )
    subparser_edit_queue.add_argument(
        "-P",
        "--priority",
        type=int,
        help="associated priority for the queue",
        default=None,
        metavar="PRIORITY",
    )
    subparser_edit_queue.add_argument(
        "--max-running-jobs",
        type=int,
        help="max number of running jobs an association can have in the queue",
        default=None,
        metavar="MAX_RUNNING_JOBS",
    )
    subparser_edit_queue.add_argument(
        "--max-nodes-per-assoc",
        type=int,
        help=(
            "max number of nodes an association can have across all of their running "
            "jobs in the queue"
        ),
        default=None,
        metavar="MAX_NODES_PER_ASSOC",
    )


def add_delete_queue_arg(subparsers):
    subparser_delete_queue = subparsers.add_parser(
        "delete-queue",
        help="remove a queue",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_delete_queue.set_defaults(func="delete_queue")
    subparser_delete_queue.add_argument("queue", help="queue name", metavar="QUEUE")


def add_add_project_arg(subparsers):
    subparser_add_project = subparsers.add_parser(
        "add-project",
        help="add a new project",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_add_project.set_defaults(func="add_project")
    subparser_add_project.add_argument(
        "project", help="project name", metavar="PROJECT"
    )


def add_view_project_arg(subparsers):
    subparser_view_project = subparsers.add_parser(
        "view-project",
        help="view project information",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_view_project.set_defaults(func="view_project")
    subparser_view_project.add_argument(
        "project", help="project name", metavar="PROJECT"
    )
    subparser_view_project.add_argument(
        "--parsable",
        action="store_const",
        const=True,
        help="print all information about a project on one line",
        metavar="PARSABLE",
    )
    subparser_view_project.add_argument(
        "-o",
        "--format",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )


def add_delete_project_arg(subparsers):
    subparser_delete_project = subparsers.add_parser(
        "delete-project",
        help="remove a project",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_delete_project.set_defaults(func="delete_project")
    subparser_delete_project.add_argument(
        "project", help="project name", metavar="PROJECT"
    )


def add_list_projects_arg(subparsers):
    subparser_list_projects = subparsers.add_parser(
        "list-projects",
        help="list all registered projects",
        formatter_class=flux.util.help_formatter(),
    )

    subparser_list_projects.set_defaults(func="list_projects")
    subparser_list_projects.add_argument(
        "--fields",
        help="list of fields to include in output",
        default=None,
        metavar="PROJECT_ID,PROJECT,USAGE",
    )
    subparser_list_projects.add_argument(
        "--json",
        action="store_const",
        const=True,
        help="list all projects in json format",
    )
    subparser_list_projects.add_argument(
        "-o",
        "--format",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )


def add_scrub_job_records_arg(subparsers):
    subparser = subparsers.add_parser(
        "scrub-old-jobs",
        help="clean job-archive of old job records",
        formatter_class=flux.util.help_formatter(),
    )

    subparser.set_defaults(func="scrub_old_jobs")
    subparser.add_argument(
        "num_weeks",
        help="delete jobs that have finished more than NUM_WEEKS ago",
        type=int,
        nargs="?",
        metavar="NUM_WEEKS",
        default=26,
    )


def add_export_db_arg(subparsers):
    subparser = subparsers.add_parser(
        "export-db",
        help="""
        Extract flux-accounting database information into two .csv files.

        Order of columns extracted from association_table:

        Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues

        If no custom path is specified, this will create a file in the
        current working directory called users.csv.

        ----------------

        Order of columns extracted from bank_table:

        Bank,ParentBank,Shares

        If no custom path is specified, this will create a file in the
        current working directory called banks.csv.

        Use these two files to populate a new flux-accounting DB with:

        flux account pop-db -b banks.csv -u users.csv
        """,
        formatter_class=flux.util.help_formatter(),
    )
    subparser.set_defaults(func="export_db")
    subparser.add_argument(
        "-u", "--users", help="path to a .csv file containing user information"
    )
    subparser.add_argument(
        "-b", "--banks", help="path to a .csv file containing bank information"
    )


def add_pop_db_arg(subparsers):
    subparser = subparsers.add_parser(
        "pop-db",
        help="""
        Description: Populate a flux-accounting database with a .csv file.

        Order of elements required for populating association_table:

        Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues

        [Shares], [MaxRunningJobs], [MaxActiveJobs], and [MaxNodes] can be left
        blank ('') in the .csv file for a given row.

        ----------------

        Order of elements required for populating bank_table:

        Bank,ParentBank,Shares

        [ParentBank] can be left blank ('') in .csv file for a given row.
        """,
        formatter_class=flux.util.help_formatter(),
    )
    subparser.set_defaults(func="pop_db")
    subparser.add_argument(
        "-u", "--users", help="path to a .csv file containing user information"
    )
    subparser.add_argument(
        "-b", "--banks", help="path to a .csv file containing bank information"
    )


def add_list_queues_arg(subparsers):
    subparser_list_queues = subparsers.add_parser(
        "list-queues",
        help="list all queues in the flux-accounting DB",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_list_queues.set_defaults(func="list_queues")
    subparser_list_queues.add_argument(
        "--fields",
        type=str,
        help="list of fields to include in JSON output",
        default=None,
        metavar="QUEUE,MIN_NODES_PER_JOB,MAX_NODES_PER_JOB,MAX_TIME_PER_JOB,PRIORITY",
    )
    subparser_list_queues.add_argument(
        "--json",
        action="store_const",
        const=True,
        help="print output in JSON format",
    )
    subparser_list_queues.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="Specify output format using Python's string format syntax.",
        metavar="FORMAT",
    )


def add_view_priority_factor_arg(subparsers):
    subparser_view_priority_factor = subparsers.add_parser(
        "view-factor",
        help="view the configuration about a particular priority factor",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_view_priority_factor.set_defaults(func="view_factor")
    subparser_view_priority_factor.add_argument(
        "factor",
        type=str,
        help="the name of the factor",
        metavar="FACTOR",
    )
    subparser_view_priority_factor.add_argument(
        "--json",
        action="store_const",
        const=True,
        help="print output in JSON format",
    )
    subparser_view_priority_factor.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="specify output format using Python's string format syntax",
        metavar="FORMAT",
    )


def add_edit_priority_factor_arg(subparsers):
    subparser_edit_priority_factor = subparsers.add_parser(
        "edit-factor",
        help="edit the integer weight for a particular priority factor",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_edit_priority_factor.set_defaults(func="edit_factor")
    subparser_edit_priority_factor.add_argument(
        "--factor",
        type=str,
        required=True,
        help="the name of the factor",
        metavar="FACTOR",
    )
    subparser_edit_priority_factor.add_argument(
        "--weight",
        type=int,
        required=True,
        help="the new integer weight for the priority factor",
        metavar="WEIGHT",
    )


def add_list_priority_factors(subparsers):
    subparser_list_factors = subparsers.add_parser(
        "list-factors",
        help="list all priority factors in the flux-accounting DB",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_list_factors.set_defaults(func="list_factors")
    subparser_list_factors.add_argument(
        "--fields",
        type=str,
        help="list of fields to include in output",
        default=None,
        metavar="FACTOR,WEIGHT",
    )
    subparser_list_factors.add_argument(
        "--json",
        action="store_const",
        const=True,
        help="print output in JSON format",
    )
    subparser_list_factors.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="specify output format using Python's string format syntax",
        metavar="FORMAT",
    )


def add_reset_priority_factors_arg(subparsers):
    subparser_reset_factors = subparsers.add_parser(
        "reset-factors",
        help="reset the priority factors and their weights to default values",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_reset_factors.set_defaults(func="reset_factors")


def add_jobs_arg(subparsers):
    subparser_jobs = subparsers.add_parser(
        "jobs",
        help="see a compact breakdown of active job's and how their priorities were calculated",
        formatter_class=flux.util.help_formatter(),
    )
    subparser_jobs.set_defaults(func="jobs")
    subparser_jobs.add_argument(
        "username",
        help="username to look up jobs for",
        type=str,
        metavar="USERNAME",
    )
    subparser_jobs.add_argument(
        "--bank",
        help="list all jobs under a certain bank",
        type=str,
        metavar="BANK",
    )
    subparser_jobs.add_argument(
        "--queue",
        help="list all jobs under a certain queue",
        type=str,
        metavar="QUEUE",
    )
    subparser_jobs.add_argument(
        "-o",
        "--format",
        type=str,
        default="",
        help="specify output format using Python's string format syntax",
        metavar="FORMAT",
    )
    subparser_jobs.add_argument(
        "-f",
        "--filter",
        help="list jobs with specific job state or result",
        metavar="STATES|RESULTS",
    )
    subparser_jobs.add_argument(
        "-c",
        "--count",
        default=0,
        help="limit output to N jobs (default shows all jobs for association)",
        metavar="N",
    )
    subparser_jobs.add_argument(
        "--since",
        type=str,
        default="0.0",
        help="include jobs that have become inactive since WHEN",
        metavar="WHEN",
    )
    subparser_jobs.add_argument(
        "-j",
        "--jobids",
        nargs="+",
        default=None,
        help="see priority for a specific job or set of jobs",
        metavar="[JOBIDS]",
    )
    subparser_jobs.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=True,
        help="see detailed priority calculation for a specific job or set of jobs",
    )


def add_show_usage_arg(subparsers):
    subparsers_visuals = subparsers.add_parser(
        "show-usage",
        help="graph job usage values from the flux-accounting database",
        formatter_class=flux.util.help_formatter(),
    )
    subparsers_visuals.set_defaults(func="show_usage")
    subparsers_visuals.add_argument(
        "table",
        help="the type of job usage data to visualize ",
        type=str,
        choices=["associations", "banks"],
    )
    subparsers_visuals.add_argument(
        "-n",
        "--limit",
        help="the number of rows to display on the bar chart",
        type=int,
        default=10,
        metavar="LIMIT",
    )


def add_synchronize_userids_arg(subparsers):
    subparsers_sync_userids = subparsers.add_parser(
        "sync-userids",
        help="synchronize userids for associations across tables",
        formatter_class=flux.util.help_formatter(),
    )
    subparsers_sync_userids.set_defaults(func="sync_userids")


def add_export_json_arg(subparsers):
    subparsers_init_plugin = subparsers.add_parser(
        "export-json",
        help=(
            "export flux-accounting database information as a JSON object (to be used "
            "to initialize the multi-factor priority plugin)"
        ),
        formatter_class=flux.util.help_formatter(),
    )
    subparsers_init_plugin.set_defaults(func="export_json")


def view_usage_report(subparsers):
    subparsers_view_usage_report = subparsers.add_parser(
        "view-usage-report",
        help="calculate usage for a user, bank, or association",
        formatter_class=flux.util.help_formatter(),
    )
    subparsers_view_usage_report.set_defaults(func="view_usage_report")
    subparsers_view_usage_report.add_argument(
        "-s",
        "--start",
        help=(
            "start time; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        metavar="DATE",
    )
    subparsers_view_usage_report.add_argument(
        "-e",
        "--end",
        help=(
            "end time; accepts multiple formats: "
            "seconds since epoch timestamp or human readable timestamp "
            "(e.g. '01/01/2025', '2025-01-01 08:00:00', 'Jan 1, 2025 8am')"
        ),
        metavar="DATE",
    )
    subparsers_view_usage_report.add_argument(
        "-u",
        "--username",
        help="only calculate usage for USERNAME",
        metavar="USERNAME",
    )
    subparsers_view_usage_report.add_argument(
        "-b",
        "--bank",
        help="only calculate usage for BANK",
        metavar="BANK",
    )
    subparsers_view_usage_report.add_argument(
        "-r",
        "--report-type",
        help="specify how data should be binned",
        metavar="bybank|byuser|byassociation",
        type=str,
        choices=["bybank", "byuser", "byassociation"],
    )
    subparsers_view_usage_report.add_argument(
        "-t",
        "--time-unit",
        help="specify time unit for data",
        metavar="hour|min|sec",
        choices=["hour", "min", "sec"],
    )
    subparsers_view_usage_report.add_argument(
        "-S",
        "--job-size-bins",
        help="bin by job sizes",
        metavar="NNODES,NNODES,...",
    )


def add_arguments_to_parser(parser, subparsers):
    add_path_arg(parser)
    add_view_user_arg(subparsers)
    add_list_users_arg(subparsers)
    add_add_user_arg(subparsers)
    add_delete_user_arg(subparsers)
    add_edit_user_arg(subparsers)
    add_view_job_records_arg(subparsers)
    add_create_db_arg(subparsers)
    add_add_bank_arg(subparsers)
    add_view_bank_arg(subparsers)
    add_delete_bank_arg(subparsers)
    add_edit_bank_arg(subparsers)
    add_list_banks_arg(subparsers)
    add_update_usage_arg(subparsers)
    add_add_queue_arg(subparsers)
    add_view_queue_arg(subparsers)
    add_edit_queue_arg(subparsers)
    add_delete_queue_arg(subparsers)
    add_add_project_arg(subparsers)
    add_view_project_arg(subparsers)
    add_delete_project_arg(subparsers)
    add_list_projects_arg(subparsers)
    add_scrub_job_records_arg(subparsers)
    add_export_db_arg(subparsers)
    add_pop_db_arg(subparsers)
    add_list_queues_arg(subparsers)
    add_view_priority_factor_arg(subparsers)
    add_edit_priority_factor_arg(subparsers)
    add_list_priority_factors(subparsers)
    add_reset_priority_factors_arg(subparsers)
    add_jobs_arg(subparsers)
    add_show_usage_arg(subparsers)
    add_edit_all_users_arg(subparsers)
    add_synchronize_userids_arg(subparsers)
    add_export_json_arg(subparsers)
    view_usage_report(subparsers)


def set_db_location(args):
    path = args.path if args.path else fluxacct.accounting.DB_PATH

    return path


def select_accounting_function(args, parser):
    data = vars(args)

    # map each command to the corresponding accounting RPC call
    func_map = {
        "view_user": "accounting.view_user",
        "list_users": "accounting.list_users",
        "add_user": "accounting.add_user",
        "delete_user": "accounting.delete_user",
        "edit_user": "accounting.edit_user",
        "view_job_records": "accounting.view_job_records",
        "add_bank": "accounting.add_bank",
        "view_bank": "accounting.view_bank",
        "delete_bank": "accounting.delete_bank",
        "edit_bank": "accounting.edit_bank",
        "list_banks": "accounting.list_banks",
        "add_queue": "accounting.add_queue",
        "view_queue": "accounting.view_queue",
        "delete_queue": "accounting.delete_queue",
        "edit_queue": "accounting.edit_queue",
        "add_project": "accounting.add_project",
        "view_project": "accounting.view_project",
        "delete_project": "accounting.delete_project",
        "list_projects": "accounting.list_projects",
        "scrub_old_jobs": "accounting.scrub_old_jobs",
        "export_db": "accounting.export_db",
        "pop_db": "accounting.pop_db",
        "list_queues": "accounting.list_queues",
        "view_factor": "accounting.view_factor",
        "edit_factor": "accounting.edit_factor",
        "list_factors": "accounting.list_factors",
        "reset_factors": "accounting.reset_factors",
        "jobs": "accounting.jobs",
        "show_usage": "accounting.show_usage",
        "edit_all_users": "accounting.edit_all_users",
        "sync_userids": "accounting.sync_userids",
        "export_json": "accounting.export_json",
        "view_usage_report": "accounting.view_usage_report",
    }

    if args.func in func_map:
        return_val = flux.Flux().rpc(func_map[args.func], data).get()
    else:
        parser.print_usage()
        return

    if list(return_val.values())[0] != 0:
        print(list(return_val.values())[0])


LOGGER = logging.getLogger("flux-account")


@flux.util.CLIMain(LOGGER)
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

    if args.func == "update_usage":
        # temporary workaround while admins adjust cron scripts to accurately
        # reflect the new "flux account-update-usage" syntax
        LOGGER.warning(
            "update-usage is deprecated. Use 'flux account-update-usage instead."
        )
        LOGGER.info("running 'flux account-update-usage locally")
        try:
            handle = flux.Flux()
            if handle.get_rank() != 0:
                raise Exception(
                    f"flux account-update-usage can only run on rank 0. "
                    f"Current rank={handle.get_rank()}"
                )
            subprocess.run(
                [
                    "flux",
                    "account-update-usage",
                    "-p",
                    path,
                    "--priority-decay-half-life",
                    str(args.priority_decay_half_life),
                ],
                check=True,
            )
        except SystemExit as exc:
            LOGGER.error("update-usage: %s", (exc))
            sys.exit(1)
        sys.exit(0)

    select_accounting_function(args, parser)


if __name__ == "__main__":
    main()
