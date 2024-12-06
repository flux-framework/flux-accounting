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
import json


class AccountingFormatter:
    def __init__(self, cursor, error_msg="no results found in query"):
        """
        Initialize an AccountingFormatter object with a SQLite cursor.

        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
        """
        self.cursor = cursor
        self.column_names = [description[0] for description in cursor.description]
        self.rows = self.cursor.fetchall()

        if not self.rows:
            # the SQL query didn't fetch any results; raise an Exception
            raise ValueError(error_msg)

    def get_column_names(self):
        """
        Return the column names from the query result.

        Returns:
            list: list of column names.
        """
        return self.column_names

    def get_rows(self):
        """
        Return all rows fetched by the cursor.

        Returns:
            list: list of tuples representing rows of data.
        """
        return self.rows

    def as_table(self):
        """
        Format a SQL query in table format.

        Returns:
            table: the data from the query formatted as a table.
        """
        # fetch column names and determine the width of each column
        col_names = [description[0] for description in self.cursor.description]
        col_widths = [
            max(len(str(value)) for value in [col] + [row[i] for row in self.rows])
            for i, col in enumerate(col_names)
        ]

        # format a row of data
        def format_row(row):
            return " | ".join(
                [f"{str(value).ljust(col_widths[i])}" for i, value in enumerate(row)]
            )

        # format the header, separator, and data rows
        header = format_row(col_names)
        separator = "-+-".join(["-" * width for width in col_widths])
        data_rows = "\n".join([format_row(row) for row in self.rows])

        table = f"{header}\n{separator}\n{data_rows}"

        return table

    def as_json(self):
        """
        Format a SQL query in JSON format.

        Returns:
            json_string: the data from the query formatted as a JSON string.
        """
        # fetch column names
        col_names = [description[0] for description in self.cursor.description]

        # create a list of dictionaries, one for each row
        table_data = [
            {col_names[i]: row[i] for i in range(len(col_names))} for row in self.rows
        ]

        # convert the list of dictionaries to a JSON string
        json_string = json.dumps(table_data, indent=2)

        return json_string


class AssociationFormatter(AccountingFormatter):
    """
    Subclass of AccountingFormatter, specific to associations in the flux-accounting
    database.
    """

    def __init__(self, cursor, username):
        """
        Initialize an AssociationFormatter object with a SQLite cursor.

        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
            username: the username of the association.
        """
        self.username = username
        super().__init__(
            cursor, error_msg=f"user {self.username} not found in association_table"
        )
