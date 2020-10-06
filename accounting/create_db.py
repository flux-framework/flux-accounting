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
                creation_time bigint(20)            NOT NULL,
                mod_time      bigint(20)  DEFAULT 0 NOT NULL,
                deleted       tinyint(4)  DEFAULT 0 NOT NULL,
                user_name     tinytext              NOT NULL,
                admin_level   smallint(6) DEFAULT 1 NOT NULL,
                bank          tinytext              NOT NULL,
                shares        int(11)     DEFAULT 1 NOT NULL,
                max_jobs      int(11)               NOT NULL,
                max_wall_pj   int(11)               NOT NULL,
                PRIMARY KEY   (user_name, bank)
        );"""
    )
    logging.info("Created association_table successfully")

    # Bank Table
    # bank_id gets auto-incremented with every new entry
    logging.info("Creating bank_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS bank_table (
                bank_id     integer PRIMARY KEY,
                bank        text    NOT NULL,
                parent_bank text,
                shares      int     NOT NULL
        );"""
    )
    logging.info("Created bank_table successfully")

    conn.close()
