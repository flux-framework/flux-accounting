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
