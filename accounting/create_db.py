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


LOGGER = logging.basicConfig(filename="accounting/db_creation.log", level=logging.INFO)


def create_db(filepath):
    # open connection to database
    logging.info("Creating Flux Accounting DB")
    conn = sqlite3.connect(filepath)
    logging.info("Created Flux Accounting DB sucessfully")

    # Association Table
    logging.info("Creating association_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS association_table (
                creation_time bigint(20)            NOT NULL,
                mod_time      bigint(20)  DEFAULT 0 NOT NULL,
                deleted       tinyint(4)  DEFAULT 0 NOT NULL,
                id_assoc      integer                         PRIMARY KEY AUTOINCREMENT,
                user_name     tinytext              NOT NULL,
                admin_level   smallint(6) DEFAULT 1 NOT NULL,
                account       tinytext              NOT NULL,
                parent_acct   tinytext,
                shares        int(11)     DEFAULT 1 NOT NULL,
                max_jobs      int(11),
                max_wall_pj   int(11)
        );"""
    )
    logging.info("Created association_table successfully")

    conn.close()


def main():
    create_db("accounting/FluxAccounting.db")


if __name__ == "__main__":
    main()
