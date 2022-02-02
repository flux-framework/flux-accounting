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
import logging
import sys
import pathlib
import math
import time


def add_usage_columns_to_table(
    conn, table_name, priority_usage_reset_period=None, priority_decay_half_life=None
):
    # the number of columns (or 'bins') holding usage factors is determined by
    # the following:
    #
    # PriorityUsageResetPeriod / PriorityDecayHalfLife
    #
    # each parameter represents a number of weeks by which to hold usage
    # factors up to the time period where jobs no longer play a factor in
    # calculating a usage factor
    column_name = "usage_factor_period_0"
    if priority_decay_half_life is not None and priority_usage_reset_period is not None:
        num_columns = math.ceil(
            int(priority_usage_reset_period) / int(priority_decay_half_life)
        )
    else:
        num_columns = 4
    for i in range(num_columns):
        alter_stmt = (
            "ALTER TABLE "
            + table_name
            + " ADD COLUMN "
            + column_name
            + " REAL DEFAULT 0.0"
        )
        conn.execute(alter_stmt)
        conn.commit()
        column_name = "usage_factor_period_" + str(i + 1)


def set_half_life_period_end(conn, priority_decay_half_life=None):
    if priority_decay_half_life is not None:
        # convert number of weeks to seconds; this will be appended
        # to the current time to represent one 'half-life' period
        # for the first usage bin
        half_life_period = int(priority_decay_half_life) * 604800
        half_life_period_end = time.time() + half_life_period
    else:
        half_life_period = 604800
        half_life_period_end = time.time() + half_life_period

    update_stmt = """
        UPDATE t_half_life_period_table
        SET end_half_life_period=?
        WHERE cluster='cluster'
        """
    conn.execute(update_stmt, (str(half_life_period_end),))
    conn.commit()


def create_db(
    filepath, priority_usage_reset_period=None, priority_decay_half_life=None
):
    db_dir = pathlib.PosixPath(filepath).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    try:
        # open connection to database
        logging.info("Creating Flux Accounting DB")
        conn = sqlite3.connect("file:" + filepath + "?mode:rwc", uri=True)
        logging.info("Created Flux Accounting DB successfully")
    except sqlite3.OperationalError as exception:
        logging.error(exception)
        sys.exit(1)

    # Association Table
    logging.info("Creating association_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS association_table (
                creation_time   bigint(20)                NOT NULL,
                mod_time        bigint(20)  DEFAULT 0     NOT NULL,
                deleted         tinyint(4)  DEFAULT 0     NOT NULL,
                username        tinytext                  NOT NULL,
                userid          int(11)     DEFAULT 65534 NOT NULL,
                bank            tinytext                  NOT NULL,
                default_bank    tinytext                  NOT NULL,
                shares          int(11)     DEFAULT 1     NOT NULL    ON CONFLICT REPLACE DEFAULT 1,
                job_usage       real        DEFAULT 0.0   NOT NULL,
                fairshare       real        DEFAULT 0.5   NOT NULL,
                max_jobs        int(11)     DEFAULT 5     NOT NULL    ON CONFLICT REPLACE DEFAULT 5,
                max_active_jobs int(11)     DEFAULT 7     NOT NULL    ON CONFLICT REPLACE DEFAULT 7,
                qos             tinytext    DEFAULT ''    NOT NULL    ON CONFLICT REPLACE DEFAULT '',
                PRIMARY KEY   (username, bank)
        );"""
    )
    logging.info("Created association_table successfully")

    # Bank Table
    # bank_id gets auto-incremented with every new entry
    logging.info("Creating bank_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS bank_table (
                bank_id     integer PRIMARY KEY AUTOINCREMENT,
                bank        text                NOT NULL,
                parent_bank text    DEFAULT '',
                shares      int                 NOT NULL
        );"""
    )
    logging.info("Created bank_table successfully")

    # Job Usage Factor Table
    # stores past job usage factors for users
    logging.info("Creating job_usage_factor table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS job_usage_factor_table (
                username            tinytext                    NOT NULL,
                userid              int(11)                     NOT NULL,
                bank                tinytext                    NOT NULL,
                last_job_timestamp  real        DEFAULT 0.0,
                PRIMARY KEY (username, bank)
        );"""
    )
    add_usage_columns_to_table(
        conn,
        "job_usage_factor_table",
        priority_usage_reset_period,
        priority_decay_half_life,
    )
    logging.info("Created job_usage_factor_table successfully")

    # Half Life Timestamp Table
    # keeps track of current half-life period
    logging.info("Creating t_half_life_period_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS t_half_life_period_table (
                cluster               tinytext DEFAULT 'cluster',
                end_half_life_period  real     DEFAULT 0.0

        );"""
    )
    conn.execute(
        """
            INSERT INTO t_half_life_period_table (cluster, end_half_life_period)
            VALUES ('cluster', 0.0);
        """
    )
    set_half_life_period_end(conn, priority_decay_half_life)
    logging.info("Created t_half_life_period_table successfully")

    # QOS Table
    # keeps track of what QOS' are defined and their associated priority
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qos_table (
            qos         tinytext        NOT NULL,
            priority    int(11)         NOT NULL,
            PRIMARY KEY (qos)
        );"""
    )

    # Queue Table
    # stores queue limit information
    logging.info("Creating queue_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS queue_table (
                queue               tinytext                NOT NULL,
                min_nodes_per_job   int(11),
                max_nodes_per_job   int(11),
                max_time_per_job    int(11),
                PRIMARY KEY (queue)
            );"""
    )

    conn.close()
