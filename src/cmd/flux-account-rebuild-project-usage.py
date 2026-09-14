#!/usr/bin/env python3

###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import argparse
import logging
import os
import sqlite3
import sys

import fluxacct.accounting
from fluxacct.accounting import job_usage_calculation as job_usage
from fluxacct.accounting import util

LOGGER = logging.getLogger(__name__)


def set_db_loc(args):
    return args.path if args.path else fluxacct.accounting.DB_PATH


def est_sqlite_conn(path):
    if not os.path.isfile(path):
        print(f"error opening DB: unable to open database file {path}", file=sys.stderr)
        return None

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True, timeout=60)
        conn.execute("PRAGMA foreign_keys = 1")
        return conn
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}", file=sys.stderr)
        return None


# pylint: disable=broad-except
def main():
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild project usage totals from retained job records. Pause job "
            "fetching and usage updates before running this command."
        )
    )
    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase verbosity of output",
    )
    args = parser.parse_args()
    util.config_logging(args.verbose, LOGGER)

    LOGGER.warning(
        "rebuilding uses retained jobs only; running this command after "
        "scrubbing jobs may lower project usage totals"
    )

    conn = est_sqlite_conn(set_db_loc(args))
    if conn is None:
        return 1

    try:
        job_usage.rebuild_project_usage(conn)
    except Exception as exc:
        LOGGER.error("unable to rebuild project usage: %s", exc)
        return 1
    finally:
        conn.close()

    LOGGER.info("project-usage rebuild complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
