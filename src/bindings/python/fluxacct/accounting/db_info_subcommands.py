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

from fluxacct.accounting.util import with_cursor


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
        queues, active, projects, default_project, max_nodes, max_cores
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
