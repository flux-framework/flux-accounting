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
import pandas as pd
import logging
import argparse
import sys


LOGGER = logging.basicConfig(filename="db_creation.log", level=logging.INFO)


def create_db(filepath):
    # open connection to database
    logging.info("Creating Flux Accounting DB")
    conn = sqlite3.connect("file:" + filepath + "?mode:rwc", uri=True)
    logging.info("Created Flux Accounting DB sucessfully")

    # Association Table
    logging.info("Creating association_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS association_table (
                id_assoc      integer                           PRIMARY KEY,
                creation_time bigint(20)            NOT NULL,
                mod_time      bigint(20)  DEFAULT 0 NOT NULL,
                deleted       tinyint(4)  DEFAULT 0 NOT NULL,
                user_name     tinytext    UNIQUE    NOT NULL,
                admin_level   smallint(6) DEFAULT 1 NOT NULL,
                account       tinytext              NOT NULL,
                parent_acct   tinytext              NOT NULL,
                shares        int(11)     DEFAULT 1 NOT NULL,
                max_jobs      int(11)               NOT NULL,
                max_wall_pj   int(11)               NOT NULL
        );"""
    )
    logging.info("Created association_table successfully")

    conn.close()


def main():

    parser = argparse.ArgumentParser(
        description="""
        Description: Create flux-accounting database to store
        user account information.
        """
    )

    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )

    args = parser.parse_args()

    path = args.path if args.path else "FluxAccounting.db"
    try:
        create_db(path)
    except sqlite3.OperationalError:
        print("Unable to create database file")
        sys.exit(-1)


if __name__ == "__main__":
    main()
