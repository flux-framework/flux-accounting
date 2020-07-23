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

from accounting import accounting_cli_functions as aclif


def main():

    parser = argparse.ArgumentParser(
        description="""
        Description: Translate command line arguments into
        SQLite instructions for the Flux Accounting Database.
        """
    )
    subparsers = parser.add_subparsers(help="sub-command help",)

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
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

    args = parser.parse_args()

    # try to open database file; will exit with -1 if database file not found
    path = args.path if args.path else "FluxAccounting.db"
    try:
        conn = sqlite3.connect("file:" + path + "?mode=rw", uri=True)
    except sqlite3.OperationalError:
        print("Unable to open database file")
        sys.exit(-1)

    try:
        if args.func == "view_user":
            aclif.view_user(conn, args.username)
        elif args.func == "add_user":
            aclif.add_user(
                conn,
                args.username,
                args.admin_level,
                args.account,
                args.parent_acct,
                args.shares,
                args.max_jobs,
                args.max_wall_pj,
            )
        elif args.func == "delete_user":
            aclif.delete_user(conn, args.username)
        elif args.func == "edit_user":
            aclif.edit_user(conn, args.username, args.field, args.new_value)
        else:
            print(parser.print_usage())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
