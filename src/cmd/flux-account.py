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
from fluxacct.accounting import qos_subcommands as q
from fluxacct.accounting import job_archive_interface as jobs
from fluxacct.accounting import create_db as c


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
        "--admin-level",
        help="admin level",
        default=1,
        metavar="ADMIN_LEVEL",
    )
    subparser_add_user.add_argument(
        "--bank",
        help="bank to charge jobs against",
        metavar="BANK",
    )
    subparser_add_user.add_argument(
        "--parent-acct",
        help="parent account",
        default="",
        metavar="PARENT_ACCOUNT",
    )
    subparser_add_user.add_argument(
        "--shares",
        help="shares",
        default=1,
        metavar="SHARES",
    )
    subparser_add_user.add_argument(
        "--max-jobs",
        help="max jobs",
        default=5,
        metavar="MAX_JOBS",
    )
    subparser_add_user.add_argument(
        "--qos",
        help="quality of service",
        default="",
        metavar="QUALITY OF SERVICE",
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
        "--username",
        help="username",
        metavar="USERNAME",
    )
    subparser_edit_user.add_argument(
        "--bank",
        help="bank",
        default="",
        metavar="BANK",
    )
    subparser_edit_user.add_argument(
        "--field",
        help="column name",
        metavar="FIELD",
    )
    subparser_edit_user.add_argument(
        "--new-value",
        help="new value",
        metavar="VALUE",
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
        "path", help="specify location of database file", metavar=("DATABASE PATH")
    )
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
        help="contribution of historical usage in weeks on the composite usage value",
        metavar="PRIORITY DECAY HALF LIFE",
    )


def add_add_qos_arg(subparsers):
    subparser_add_qos = subparsers.add_parser("add-qos", help="add a new qos")

    subparser_add_qos.set_defaults(func="add_qos")
    subparser_add_qos.add_argument("--qos", help="QOS name", metavar="QOS")
    subparser_add_qos.add_argument(
        "--priority", help="QOS priority", metavar="PRIORITY"
    )


def add_view_qos_arg(subparsers):
    subparser_view_qos = subparsers.add_parser("view-qos", help="view QOS information")

    subparser_view_qos.set_defaults(func="view_qos")
    subparser_view_qos.add_argument("--qos", help="QOS name", metavar="QOS")


def add_edit_qos_arg(subparsers):
    subparser_edit_qos = subparsers.add_parser("edit-qos", help="edit a QOS' priority")

    subparser_edit_qos.set_defaults(func="edit_qos")
    subparser_edit_qos.add_argument("--qos", help="qos name", metavar="QOS")
    subparser_edit_qos.add_argument(
        "--priority", help="new priority", metavar="PRIORITY"
    )


def add_delete_qos_arg(subparsers):
    subparser_delete_qos = subparsers.add_parser("delete-qos", help="remove a QOS")
    subparser_delete_qos.set_defaults(func="delete_qos")
    subparser_delete_qos.add_argument("--qos", help="QOS name", metavar="QOS")


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
    add_add_qos_arg(subparsers)
    add_view_qos_arg(subparsers)
    add_edit_qos_arg(subparsers)
    add_delete_qos_arg(subparsers)


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
    except sqlite3.OperationalError:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
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
            args.admin_level,
            args.shares,
            args.max_jobs,
            args.qos,
        )
    elif args.func == "delete_user":
        u.delete_user(conn, args.username, args.bank)
    elif args.func == "edit_user":
        u.edit_user(conn, args.username, args.field, args.new_value, args.bank)
    elif args.func == "view_job_records":
        jobs.view_job_records(
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
        b.view_bank(conn, args.bank)
    elif args.func == "delete_bank":
        b.delete_bank(conn, args.bank)
    elif args.func == "edit_bank":
        b.edit_bank(conn, args.bank, args.shares)
    elif args.func == "update_usage":
        jobs_conn = establish_sqlite_connection(args.job_archive_db_path)
        jobs.update_job_usage(conn, jobs_conn, args.priority_decay_half_life)
    elif args.func == "add_qos":
        q.add_qos(conn, args.qos, args.priority)
    elif args.func == "view_qos":
        q.view_qos(conn, args.qos)
    elif args.func == "edit_qos":
        q.edit_qos(conn, args.qos, args.priority)
    elif args.func == "delete_qos":
        q.delete_qos(conn, args.qos)
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
            args.path, args.priority_usage_reset_period, args.priority_decay_half_life
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
