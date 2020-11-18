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

import pandas as pd

from flux.accounting import accounting_cli_functions as aclif
from flux.accounting import job_archive_interface as jobs
from flux.accounting import create_db as c
from flux.accounting import print_hierarchy as ph


def main():

    parser = argparse.ArgumentParser(
        description="""
        Description: Translate command line arguments into
        SQLite instructions for the Flux Accounting Database.
        """
    )
    subparsers = parser.add_subparsers(help="sub-command help",
                                       dest="subcommand")
    subparsers.required = True

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )

    parser.add_argument(
        "-o",
        "--output-file",
        dest="output_file",
        help="specify location of output file",
    )

    subparser_view_user = subparsers.add_parser(
        "view-user", help="view a user's information in the accounting database"
    )
    subparser_view_user.set_defaults(func="view_user")
    subparser_view_user.add_argument("username", help="username", metavar=("USERNAME"))

    subparser_add_user = subparsers.add_parser(
        "add-user", help="add a user to the accounting database"
    )
    subparser_add_user.set_defaults(func="add_user")
    subparser_add_user.add_argument(
        "--username", help="username", metavar="USERNAME",
    )
    subparser_add_user.add_argument(
        "--admin-level", help="admin level", default=1, metavar="ADMIN_LEVEL",
    )
    subparser_add_user.add_argument(
        "--account", help="account to charge jobs against", metavar="ACCOUNT",
    )
    subparser_add_user.add_argument(
        "--parent-acct", help="parent account", default="", metavar="PARENT_ACCOUNT",
    )
    subparser_add_user.add_argument(
        "--shares", help="shares", default=1, metavar="SHARES",
    )
    subparser_add_user.add_argument(
        "--max-jobs", help="max jobs", default=1, metavar="MAX_JOBS",
    )
    subparser_add_user.add_argument(
        "--max-wall-pj",
        help="max wall time per job",
        default=60,
        metavar="MAX_WALL_PJ",
    )

    subparser_delete_user = subparsers.add_parser(
        "delete-user", help="remove a user from the accounting database"
    )
    subparser_delete_user.set_defaults(func="delete_user")
    subparser_delete_user.add_argument(
        "username", help="username", metavar=("USERNAME")
    )

    subparser_edit_user = subparsers.add_parser("edit-user", help="edit a user's value")
    subparser_edit_user.set_defaults(func="edit_user")
    subparser_edit_user.add_argument(
        "--username", help="username", metavar="USERNAME",
    )
    subparser_edit_user.add_argument(
        "--field", help="column name", metavar="FIELD",
    )
    subparser_edit_user.add_argument(
        "--new-value", help="new value", metavar="VALUE",
    )

    subparser_view_job_records = subparsers.add_parser(
        "view-job-records", help="view job records"
    )
    subparser_view_job_records.set_defaults(func="view_job_records")
    subparser_view_job_records.add_argument(
        "-u", "--user", help="username", metavar="USERNAME",
    )
    subparser_view_job_records.add_argument(
        "-j", "--jobid", help="jobid", metavar="JOBID"
    )
    subparser_view_job_records.add_argument(
        "-a", "--after-start-time", help="start time", metavar="START TIME",
    )
    subparser_view_job_records.add_argument(
        "-b", "--before-end-time", help="end time", metavar="END TIME",
    )

    subparser_create_db = subparsers.add_parser(
        "create-db", help="create the flux-accounting database"
    )
    subparser_create_db.set_defaults(func="create_db")
    subparser_create_db.add_argument(
        "dbpath", help="specify location of database file", metavar=("DATABASE PATH")
    )

    subparser_add_bank = subparsers.add_parser("add-bank", help="add a new bank")
    subparser_add_bank.set_defaults(func="add_bank")
    subparser_add_bank.add_argument(
        "bank", help="bank name", metavar="BANK",
    )
    subparser_add_bank.add_argument(
        "--parent-bank", help="parent bank name", default="", metavar="PARENT BANK"
    )
    subparser_add_bank.add_argument(
        "shares", help="number of shares to allocate to bank", metavar="SHARES"
    )

    subparser_view_bank = subparsers.add_parser(
        "view-bank", help="view bank information"
    )
    subparser_view_bank.set_defaults(func="view_bank")
    subparser_view_bank.add_argument(
        "bank", help="bank name", metavar="BANK",
    )

    subparser_delete_bank = subparsers.add_parser("delete-bank", help="remove a bank")
    subparser_delete_bank.set_defaults(func="delete_bank")
    subparser_delete_bank.add_argument(
        "bank", help="bank name", metavar="BANK",
    )

    subparser_edit_bank = subparsers.add_parser(
        "edit-bank", help="edit a bank's allocation"
    )
    subparser_edit_bank.set_defaults(func="edit_bank")
    subparser_edit_bank.add_argument(
        "bank", help="bank", metavar="BANK",
    )
    subparser_edit_bank.add_argument(
        "--shares", help="new shares value", metavar="SHARES",
    )

    subparser_print_hierarchy = subparsers.add_parser(
        "print-hierarchy", help="print accounting database"
    )
    subparser_print_hierarchy.set_defaults(func="print_hierarchy")

    args = parser.parse_args()

    # if we are creating the DB for the first time, we need
    # to ONLY create the DB and then exit out successfully
    if args.func == "create_db":
        c.create_db(args.dbpath)
        sys.exit(0)

    # try to open database file; will exit with -1 if database file not found
    path = args.path if args.path else "FluxAccounting.db"
    try:
        conn = sqlite3.connect("file:" + path + "?mode=rw", uri=True)
    except sqlite3.OperationalError:
        print("Unable to open database file")
        sys.exit(1)

    # set path for output file
    output_file = args.output_file if args.output_file else None

    try:
        if args.func == "view_user":
            aclif.view_user(conn, args.username)
        elif args.func == "add_user":
            aclif.add_user(
                conn,
                args.username,
                args.account,
                args.admin_level,
                args.shares,
                args.max_jobs,
                args.max_wall_pj,
            )
        elif args.func == "delete_user":
            aclif.delete_user(conn, args.username)
        elif args.func == "edit_user":
            aclif.edit_user(conn, args.username, args.field, args.new_value)
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
            aclif.add_bank(conn, args.bank, args.shares, args.parent_bank)
        elif args.func == "view_bank":
            aclif.view_bank(conn, args.bank)
        elif args.func == "delete_bank":
            aclif.delete_bank(conn, args.bank)
        elif args.func == "edit_bank":
            aclif.edit_bank(conn, args.bank, args.shares)
        elif args.func == "print_hierarchy":
            print(ph.print_full_hierarchy(conn))
        else:
            print(parser.print_usage())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
