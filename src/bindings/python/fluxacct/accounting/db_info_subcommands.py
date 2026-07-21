#!/usr/bin/env python3

###############################################################
# Copyright 2024 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import csv
import sqlite3
import json
import math
import time

import fluxacct
from fluxacct.accounting.util import with_cursor
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql
from flux.util import parse_fsd


@with_cursor
def reconfigure_usage_bins(conn, cursor):
    """
    Update the usage bin configuration for all associations from scratch. This function
    should be called *after* the admin has updated priority_decay_half_life,
    priority_usage_reset_period, and/or decay_factor in config_table.

    Args:
        conn: The SQLite Connection object.
        cursor: The SQLite Cursor object.
    """
    # read the new configuration from config_table
    cursor.execute(
        "SELECT value FROM config_table WHERE key='priority_decay_half_life'"
    )
    half_life = cursor.fetchone()

    cursor.execute(
        "SELECT value FROM config_table WHERE key='priority_usage_reset_period'"
    )
    reset_period = cursor.fetchone()

    if half_life is None or reset_period is None:
        raise ValueError(
            "priority_decay_half_life and priority_usage_reset_period must be set in "
            "config_table before reconfiguring usage bins"
        )

    new_half_life = float(half_life[0])
    new_reset_period = float(reset_period[0])
    new_num_periods = math.ceil(new_reset_period / new_half_life)

    # fetch all associations
    cursor.execute(
        "SELECT DISTINCT username, userid, bank FROM job_usage_per_association_table"
    )
    associations = cursor.fetchall()

    try:
        # delete all existing period rows for every association
        cursor.execute("DELETE FROM job_usage_per_association_table")

        # re-insert the correct number of period rows for every association
        # initialized to 0.0 under the new configuration
        for username, userid, bank in associations:
            for period in range(new_num_periods):
                cursor.execute(
                    """
                    INSERT INTO job_usage_per_association_table
                    (username, userid, bank, period, value)
                    VALUES (?, ?, ?, ?, 0.0)
                    """,
                    (username, userid, bank, period),
                )

        # reset last_job_timestamp for all associations so that update_job_usage()
        # replays all jobs from scratch
        cursor.execute("UPDATE job_usage_factor_table SET last_job_timestamp=0")

        # reset the half-life period end timestamp so that update_job_usage() starts
        # a fresh half-life window
        cursor.execute(
            """
            UPDATE t_half_life_period_table
            SET end_half_life_period=?
            WHERE cluster='cluster'
            """,
            (str(time.time() + new_half_life),),
        )
        cursor.execute(
            "INSERT INTO config_table (key, value) "
            "VALUES ('reconfigure_time', ?) ON CONFLICT(key)"
            "DO UPDATE SET value = excluded.value",
            (time.time(),),
        )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(
            f"failed to reconfigure usage bins, rolled back all changes: {exc}"
        )


def export_db_info(conn):
    """
    Export all of the information from the tables in the flux-accounting DB into
    separate .csv files.
    """
    cur = conn.cursor()
    # get all tables from DB
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()

    # loop through each table and export it to a separate .csv file
    for table_name in tables:
        output_csv = f"{table_name['name']}.csv"
        cur.execute(f"SELECT * FROM {table_name['name']}")
        rows = cur.fetchall()
        column_names = [description[0] for description in cur.description]

        # write data to .csv file
        with open(output_csv, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(column_names)
            writer.writerows(rows)


def populate_db(conn, csv_file, columns_included=None):
    """
    Populate an existing table from a single .csv file with an option
    to specify columns to include. The .csv file must have the column names in
    the first line to indicate which columns to insert into the table.

    Args:
        csv_file: Path to the .csv file. The name of the .csv file must match the
            name of the table in the flux-accounting DB.

        columns_included (list, optional): List of columns to include from the .csv
            file. If None, it will include all columns listed in the .csv file.

    Raises:
        ValueError: If the table derived from the .csv file name does not match
            any of the tables in the flux-accounting DB.
    """
    try:
        cur = conn.cursor()

        # extract table name from .csv filename; check if it exists in DB
        table_name = csv_file.split("/")[-1].replace(".csv", "")
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cur.fetchall()]

        if table_name not in tables:
            raise ValueError(
                f'pop-db: table "{table_name}" does not exist in the database'
            )

        with open(csv_file, "r", newline="") as file:
            reader = csv.reader(file)
            all_columns = next(reader)  # column names

            if columns_included:
                # filter only the columns specified
                columns = [col for col in all_columns if col in columns_included]
            else:
                columns = all_columns

            for row in reader:
                # build a list of (column, value) pairs for columns with non-empty values
                column_value_pairs = [
                    (columns[i], row[i]) for i in range(len(columns)) if row[i] != ""
                ]
                if column_value_pairs:
                    # separate columns and values for the SQL statement
                    cols_to_insert = [pair[0] for pair in column_value_pairs]
                    vals_to_insert = [pair[1] for pair in column_value_pairs]
                    insert_sql = (
                        f"INSERT INTO {table_name} "
                        f"({', '.join(cols_to_insert)}) "
                        f"VALUES ({', '.join(['?' for _ in vals_to_insert])})"
                    )

                    # execute the insertion with only the non-empty values
                    cur.execute(insert_sql, vals_to_insert)

        conn.commit()
    except sqlite3.OperationalError as exc:
        # roll back any changes made to the DB while trying to populate it before
        # raising an exception to the flux-accounting service
        conn.rollback()
        raise sqlite3.OperationalError(exc)


@with_cursor
def export_as_json(conn, cursor):
    """
    Return a JSON object of certain tables in the flux-accounting database, which can
    be used to initialize the multi-factor priority plugin.

    Args:
        conn: A SQLite connection object.
        cursor: A SQLite cursor object.
    Returns:
        A JSON string containing flux-accounting database information.
    """
    conn.row_factory = sqlite3.Row
    associations = []
    queues = []
    projects = []
    banks = []
    priority_factors = []
    config = {}  # will store all of the above lists

    # fetch all rows from association_table
    for row in cursor.execute(
        """SELECT userid, bank, default_bank,
        fairshare, max_running_jobs, max_active_jobs,
        queues, active, projects, default_project, max_nodes, max_cores, max_sched_jobs
        FROM association_table"""
    ):
        # create a JSON payload with the results of the query
        association = {
            "userid": int(row["userid"]),
            "bank": str(row["bank"]),
            "def_bank": str(row["default_bank"]),
            "fairshare": float(row["fairshare"]),
            "max_running_jobs": int(row["max_running_jobs"]),
            "max_active_jobs": int(row["max_active_jobs"]),
            "queues": str(row["queues"]),
            "active": int(row["active"]),
            "projects": str(row["projects"]),
            "def_project": str(row["default_project"]),
            "max_nodes": int(row["max_nodes"]),
            "max_cores": int(row["max_cores"]),
            "max_sched_jobs": int(row["max_sched_jobs"]),
        }
        associations.append(association)

    config["associations"] = associations

    # fetch all rows from queue_table
    for row in cursor.execute("SELECT * FROM queue_table"):
        # create a JSON payload with the results of the query
        queue = {
            "queue": str(row["queue"]),
            "min_nodes_per_job": int(row["min_nodes_per_job"]),
            "max_nodes_per_job": int(row["max_nodes_per_job"]),
            "max_time_per_job": int(row["max_time_per_job"]),
            "priority": int(row["priority"]),
            "max_running_jobs": int(row["max_running_jobs"]),
            "max_nodes_per_assoc": int(row["max_nodes_per_assoc"]),
            "max_sched_jobs": int(row["max_sched_jobs"]),
            "max_sched_nodes_per_assoc": int(row["max_sched_nodes_per_assoc"]),
            "max_sched_cores_per_assoc": int(row["max_sched_cores_per_assoc"]),
        }
        queues.append(queue)

    config["queues"] = queues

    # fetch all rows from project_table
    for row in cursor.execute("SELECT project FROM project_table"):
        # create a JSON payload with the results of the query
        project = {
            "project": str(row["project"]),
        }
        projects.append(project)

    config["projects"] = projects

    # fetch rows from bank_table
    for row in cursor.execute("SELECT bank, priority FROM bank_table"):
        bank = {
            "bank": str(row["bank"]),
            "priority": float(row["priority"]),
        }
        banks.append(bank)

    config["banks"] = banks

    # fetch rows from priority_factor_weight_table
    for row in cursor.execute("SELECT * FROM priority_factor_weight_table"):
        factor = {
            "factor": str(row["factor"]),
            "weight": int(row["weight"]),
        }
        priority_factors.append(factor)

    config["priority_factors"] = priority_factors

    # return a single JSON object containing the above DB information
    return json.dumps(config)


@with_cursor
def add_config(conn, cursor, key_value_string):
    """
    Add a key-value pair to config_table.

    Args:
        conn: The SQLite Connection object.
        cursor: The SQLite Cursor object.
        key_value_string: A key=value string to add to config_table.
    """
    if key_value_string.count("=") != 1:
        raise ValueError('key-value string must contain exactly one "="')
    key, value = key_value_string.split("=")
    cursor.execute(
        "INSERT INTO config_table (key, value) VALUES (?, ?)",
        (
            key,
            value,
        ),
    )

    return 0


@with_cursor
def edit_config(conn, cursor, key_value_strings):
    """
    Edit one or more key-value pairs in config_table.

    Args:
        conn: The SQLite Connection object.
        cursor: The SQLite Cursor object.
        key_value_strings: A list of key=value strings to update in config_table.
    """
    bin_config_keys = {"priority_usage_reset_period", "priority_decay_half_life"}
    usage_config_keys = {"node_weight", "core_weight", "gpu_weight"}
    requires_rebin = False

    for key_value_string in key_value_strings:
        key, value = key_value_string.split("=")

        if key in usage_config_keys:
            # ensure that weight is a floating-point value
            float(value)
        if key in bin_config_keys:
            # parse value as Flux Standard Duration (FSD)
            value = parse_fsd(str(value))
            requires_rebin = True
        if key == "decay_factor":
            if (float(value) < 0) or (float(value) > 1):
                raise ValueError(
                    "decay_factor must be a floating-point value between 0 and 1"
                )
            requires_rebin = True
        cursor.execute(
            "UPDATE config_table SET value=? WHERE key=?",
            (value, key),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"key {key} not found in config_table")

    if requires_rebin:
        # pylint: disable=no-value-for-parameter
        reconfigure_usage_bins(conn)

    conn.commit()
    return 0


@with_cursor
def delete_config(conn, cursor, key):
    """
    Delete a key-value pair from config_table.
    """
    if key in [
        "priority_usage_reset_period",
        "priority_decay_half_life",
        "decay_factor",
        "node_weight",
        "core_weight",
        "gpu_weight",
    ]:
        raise ValueError(
            "key-value pair is not allowed to be removed from config_table"
        )

    cursor.execute("DELETE FROM config_table WHERE key=?", (key,))

    return 0


@with_cursor
def view_config(conn, cursor, key, json_fmt=False, format_string=""):
    """
    View a key-value pair from config_table.
    """
    cursor.execute("SELECT * FROM config_table WHERE key=?", (key,))
    formatter = fmt.KeyValueFormatter(cursor, key)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()


@with_cursor
def list_configs(conn, cursor, cols=None, json_fmt=False, format_string=""):
    """
    List all of the key-value pairs in config_table.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.CONFIG_TABLE

    sql.validate_columns(cols, fluxacct.accounting.CONFIG_TABLE)
    # construct SELECT statement
    select_stmt = f"SELECT {', '.join(cols)} FROM config_table"
    cursor.execute(select_stmt)

    # initialize AccountingFormatter object
    formatter = fmt.AccountingFormatter(cursor)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()
