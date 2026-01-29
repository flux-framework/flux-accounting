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

import fluxacct.accounting

LOGGER = logging.getLogger(__name__)


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
        LOGGER.info("Creating Flux Accounting DB")
        conn = sqlite3.connect("file:" + filepath + "?mode:rwc", uri=True)
        LOGGER.info("Created Flux Accounting DB successfully")
    except sqlite3.OperationalError as exception:
        LOGGER.error(exception)
        sys.exit(1)

    # set version number of database
    conn.execute("PRAGMA user_version = %d" % (fluxacct.accounting.DB_SCHEMA_VERSION))

    # Association Table
    LOGGER.info("Creating association_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS association_table (
                creation_time    bigint(20)                         NOT NULL,
                mod_time         bigint(20)  DEFAULT 0              NOT NULL,
                active           int(11)     DEFAULT 1              NOT NULL,
                username         tinytext                           NOT NULL,
                userid           int(11)     DEFAULT 65534          NOT NULL,
                bank             tinytext                           NOT NULL,
                default_bank     tinytext                           NOT NULL,
                shares           int(11)     DEFAULT 1              NOT NULL    ON CONFLICT REPLACE DEFAULT 1,
                job_usage        real        DEFAULT 0.0            NOT NULL,
                fairshare        real        DEFAULT 0.5            NOT NULL    ON CONFLICT REPLACE DEFAULT 0.5,
                max_running_jobs int(11)     DEFAULT 5              NOT NULL    ON CONFLICT REPLACE DEFAULT 5,
                max_active_jobs  int(11)     DEFAULT 7              NOT NULL    ON CONFLICT REPLACE DEFAULT 7,
                max_nodes        int(11)     DEFAULT 2147483647     NOT NULL    ON CONFLICT REPLACE DEFAULT 2147483647,
                max_cores        int(11)     DEFAULT 2147483647     NOT NULL    ON CONFLICT REPLACE DEFAULT 2147483647,
                queues           tinytext    DEFAULT ''             NOT NULL    ON CONFLICT REPLACE DEFAULT '',
                projects         tinytext    DEFAULT '*'            NOT NULL    ON CONFLICT REPLACE DEFAULT '*',
                default_project  tinytext    DEFAULT '*'            NOT NULL    ON CONFLICT REPLACE DEFAULT '*',
                max_sched_jobs   int(11)     DEFAULT 2147483647     NOT NULL    ON CONFLICT REPLACE DEFAULT 2147483647,
                PRIMARY KEY   (username, bank)
        );"""
    )
    LOGGER.info("Created association_table successfully")

    # Bank Table
    # bank_id gets auto-incremented with every new entry
    LOGGER.info("Creating bank_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS bank_table (
                bank_id           integer    PRIMARY KEY AUTOINCREMENT,
                bank              text                   NOT NULL,
                active            int(11)    DEFAULT 1   NOT NULL,
                parent_bank       text       DEFAULT '',
                shares            int                    NOT NULL,
                job_usage         real       DEFAULT 0.0 NOT NULL,
                priority          real       DEFAULT 0.0 NOT NULL    ON CONFLICT REPLACE DEFAULT 0.0,
                ignore_older_than bigint(20) DEFAULT 0
        );"""
    )
    LOGGER.info("Created bank_table successfully")

    # Job Usage Factor Table
    # stores past job usage factors for users
    LOGGER.info("Creating job_usage_factor table in DB...")
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
    LOGGER.info("Created job_usage_factor_table successfully")

    # Half Life Timestamp Table
    # keeps track of current half-life period
    LOGGER.info("Creating t_half_life_period_table in DB...")
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
    LOGGER.info("Created t_half_life_period_table successfully")

    # Queue Table
    # stores queues, associated priorities, and limit information
    LOGGER.info("Creating queue_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS queue_table (
                queue               tinytext                      NOT NULL,
                min_nodes_per_job   int(11)    DEFAULT 1          NOT NULL ON CONFLICT REPLACE DEFAULT 1,
                max_nodes_per_job   int(11)    DEFAULT 1          NOT NULL ON CONFLICT REPLACE DEFAULT 1,
                max_time_per_job    int(11)    DEFAULT 60         NOT NULL ON CONFLICT REPLACE DEFAULT 60,
                priority            int(11)    DEFAULT 0          NOT NULL ON CONFLICT REPLACE DEFAULT 0,
                max_running_jobs    int(11)    DEFAULT 100        NOT NULL ON CONFLICT REPLACE DEFAULT 100,
                max_nodes_per_assoc int(11)    DEFAULT 2147483647 NOT NULL ON CONFLICT REPLACE DEFAULT 2147483647,
                PRIMARY KEY (queue)
            );"""
    )

    # Projects Table
    # stores projects
    LOGGER.info("Creating project_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS project_table (
                project_id          integer    PRIMARY KEY AUTOINCREMENT,
                project             tinytext               NOT NULL,
                usage               real       DEFAULT 0.0 NOT NULL
            );"""
    )
    conn.execute("INSERT INTO project_table (project) VALUES ('*')")
    conn.commit()

    # Jobs Table
    # stores job records for associations
    LOGGER.info("Creating jobs table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS jobs (
                id                  char(16)   PRIMARY KEY NOT NULL,
                userid              integer                NOT NULL,
                t_submit            real                   NOT NULL,
                t_run               real                   NOT NULL,
                t_inactive          real                   NOT NULL,
                ranks               text                   NOT NULL,
                R                   text                   NOT NULL,
                jobspec             text                   NOT NULL,
                project             text,
                bank                text,
                requested_duration  real       DEFAULT 0.0,
                actual_duration     real       DEFAULT 0.0
            );"""
    )
    LOGGER.info("Created jobs table successfully")

    # Priority Factor Table
    # stores the weights for each priority factor to be used in the plugin
    LOGGER.info("Creating priority_factor_weight_table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS priority_factor_weight_table (
                factor      text     PRIMARY KEY NOT NULL,
                weight      integer              NOT NULL
            );"""
    )
    LOGGER.info("Created priority_factor_weight_table successfully")
    # create and set the default weights for each factor
    conn.execute(
        f"INSERT INTO priority_factor_weight_table "
        f"VALUES ('fairshare', {fluxacct.accounting.FSHARE_WEIGHT_DEFAULT});"
    )
    conn.execute(
        f"INSERT INTO priority_factor_weight_table "
        f"VALUES ('queue', {fluxacct.accounting.QUEUE_WEIGHT_DEFAULT});"
    )
    conn.execute(
        f"INSERT INTO priority_factor_weight_table "
        f"VALUES ('bank', {fluxacct.accounting.BANK_WEIGHT_DEFAULT});"
    )
    conn.execute(
        f"INSERT INTO priority_factor_weight_table "
        f"VALUES ('urgency', {fluxacct.accounting.URGENCY_WEIGHT_DEFAULT});"
    )
    conn.commit()

    conn.close()
