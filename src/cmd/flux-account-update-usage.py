#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import logging
import sqlite3
import argparse
import sys
import os

import fluxacct.accounting
from fluxacct.accounting import job_usage_calculation as job_usage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


def set_db_loc(args):
    path = args.path if args.path else fluxacct.accounting.DB_PATH

    return path


def est_sqlite_conn(path):
    # try to open database file; will exit if database file not found
    if not os.path.isfile(path):
        print(f"error opening DB: unable to open database file {path}", file=sys.stderr)
        sys.exit(-1)

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        # set foreign keys constraint
        conn.execute("PRAGMA foreign_keys = 1")
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(-1)

    return conn


def main():
    parser = argparse.ArgumentParser(
        description="""
        Description: Update the job usage values for every association and bank
        in the flux-accounting database.
        """
    )

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    parser.add_argument(
        "--priority-decay-half-life",
        default=1,
        type=int,
        help="number of weeks for a job's usage contribution to a half-life decay",
        metavar="PRIORITY_DECAY_HALF_LIFE",
    )
    args = parser.parse_args()

    path = set_db_loc(args)
    conn = est_sqlite_conn(path)

    job_usage.update_job_usage(conn, args.priority_decay_half_life)


if __name__ == "__main__":
    main()
