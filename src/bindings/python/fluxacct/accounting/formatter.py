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
import string

import flux.util


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

    def as_format_string(self, format_string):
        """
        Return the output as a formatted string with the results of the query.

        Args:
            format_string (str): A format string defining how each row should be
                formatted. Column names should be used as placeholders.

        Returns:
            str: A formatted string containing the query results, including column headers.
        """
        try:
            header = format_string.format(
                **dict(zip(self.column_names, self.column_names))
            )
            formatted_rows = [
                format_string.format(**dict(zip(self.column_names, row)))
                for row in self.rows
            ]

            return "\n".join([header] + formatted_rows)
        except KeyError as exc:
            # one of the column names in the format string is invalid; raise ValueError
            raise ValueError(
                f"Invalid column name in format string: {exc.args[0]}."
                + f"\nAvailable columns: {','.join(self.column_names)}"
            )


class BankFormatter(AccountingFormatter):
    """
    Subclass of AccountingFormatter that includes additional methods for printing
    out banks/sub-banks in a hierarchical format and lists of users under banks.
    """

    def __init__(self, cursor, bank_name):
        """
        Initialize a BankFormatter object with a SQLite cursor.
        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
            bank_name: the name of the bank.
        """
        self.bank_name = bank_name
        super().__init__(
            cursor, error_msg=f"bank {self.bank_name} not found in bank_table"
        )

    def as_tree(self):
        """
        Format the flux-accounting bank hierarchy in tree format. The bank passed
        into the query will serve as the root of the tree.

        Returns:
            hierarchy: the hierarchy of banks in bank_table with the passed-in bank
                as the root of the tree.
        """

        def construct_hierarchy(cur, bank, hierarchy, indent=""):
            """
            Recursively traverse bank_table and look for sub banks and associations. Add
            them to the string representing the hierarchy of banks and users.

            Args:
                cur: the SQLite Cursor object used to execute SQL queries.
                bank: the current bank being passed to the SQL query.
                hierarchy: the string representing the hierarchy of banks and users.
                indent: the level of indent for each level of sub bank or users.
                    Each traversed level will have one additional space (" ") before the
                    row.
            """
            select_stmt = (
                "SELECT bank,shares,job_usage FROM bank_table WHERE parent_bank=?"
            )
            cur.execute(select_stmt, (bank,))
            sub_banks = cur.fetchall()

            if len(sub_banks) == 0:
                # reached a bank with no sub banks, so get associations under this bank
                cur.execute(
                    "SELECT username,shares,job_usage,fairshare FROM association_table WHERE bank=?",
                    (bank,),
                )
                users = cur.fetchall()
                if users:
                    for user in users:
                        hierarchy += (
                            indent
                            + " "
                            + bank.ljust(20)
                            + str(user[0]).rjust(20 - (len(indent) + 1))
                            + str(user[1]).rjust(20)
                            + str(user[2]).rjust(20)
                            + str(user[3]).rjust(20)
                            + "\n"
                        )
            else:
                # continue traversing the hierarchy
                for sub_bank in sub_banks:
                    hierarchy += (
                        indent
                        + " "
                        + str(sub_bank[0]).ljust(20)
                        + "".rjust(
                            20 - (len(indent) + 1)
                        )  # this skips the "Username" column
                        + str(sub_bank[1]).rjust(20)
                        + str(sub_bank[2]).rjust(20)
                        + "\n"
                    )
                    hierarchy = construct_hierarchy(
                        cur, sub_bank[0], hierarchy, indent + " "
                    )

            return hierarchy

        # construct header of the hierarchy
        hierarchy = (
            "Bank".ljust(20)
            + "Username".rjust(20)
            + "RawShares".rjust(20)
            + "RawUsage".rjust(20)
            + "Fairshare".rjust(20)
            + "\n"
        )
        # add the bank passed in to the hierarchy string
        hierarchy += (
            self.rows[0][1].ljust(20)
            + "".rjust(20)
            + str(self.rows[0][4]).rjust(20)
            + str(round(self.rows[0][5], 2)).rjust(20)
            + "\n"
        )

        hierarchy = construct_hierarchy(self.cursor, self.rows[0][1], hierarchy, "")
        return hierarchy

    def as_parsable_tree(self, bank):
        """
        Format the flux-accounting bank hierarchy in a parsable tree format starting with
        the bank passed in serving as the root of the tree. Delimit the items in each row
        with a pipe ('|') character.

        Returns:
            hierarchy: a string representing the hierarchy of banks in the
                flux-accounting DB as a parsable tree.
        """

        def construct_parsable_hierarchy(cur, bank, hierarchy, indent=""):
            """
            Recursively traverse bank_table and look for sub banks and users and add
            them to a string representing the flux-accounting bank hierarchy..

            Args:
                cur: the SQLite Cursor object used to execute SQL queries.
                bank: the current bank being passed to the SQL query.
                hierarchy: the string holding the parsable hierarchy tree.
                indent: the level of indent for each level of sub bank or associations.
                    Each traversed level will have one additional space " " before the
                    row.
            """
            select_stmt = (
                "SELECT bank,shares,job_usage FROM bank_table WHERE parent_bank=?"
            )
            cur.execute(select_stmt, (bank,))
            sub_banks = cur.fetchall()

            if len(sub_banks) == 0:
                # reached a bank with no sub banks, so get associations under this bank
                cur.execute(
                    "SELECT username,shares,job_usage,fairshare FROM association_table WHERE bank=?",
                    (bank,),
                )
                users = cur.fetchall()
                if users:
                    for user in users:
                        hierarchy += (
                            f"{indent} {bank}|{user['username']}|{user['shares']}|"
                            f"{user['job_usage']}|{user['fairshare']}\n"
                        )

            else:
                # continue traversing the hierarchy
                for sub_bank in sub_banks:
                    hierarchy += (
                        f"{indent} {str(sub_bank['bank'])}||{str(sub_bank['shares'])}|"
                        f"{str(sub_bank['job_usage'])}\n"
                    )
                    hierarchy = construct_parsable_hierarchy(
                        cur, sub_bank["bank"], hierarchy, indent + " "
                    )

            return hierarchy

        # construct a hierarchy string starting with the bank passed in
        hierarchy = "Bank|Username|RawShares|RawUsage|Fairshare\n"
        hierarchy += f"{self.rows[0]['bank']}||{str(self.rows[0]['shares'])}|{str(round(self.rows[0]['job_usage'], 2))}\n"
        hierarchy = construct_parsable_hierarchy(self.cursor, bank, hierarchy, "")
        return hierarchy

    def with_users(self, bank):
        """
        Print basic information for all of the users under a given bank in table
        format.

        Returns:
            info: the information for both the bank and basic information for all
                users under that bank.
        """
        try:
            info = self.as_table()

            select_stmt = """SELECT username,default_bank,shares,job_usage,fairshare
                             FROM association_table
                             WHERE bank=?"""
            self.cursor.execute(
                select_stmt,
                (bank,),
            )

            formatter = AccountingFormatter(self.cursor)
            info += "\n\n" + formatter.as_table()
            return info
        except ValueError:
            return info + f"\n\nno users under {bank}"


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

    def list_banks(self):
        """
        Return all of the banks that the user belongs to with each bank
        on its own line.
        """
        self.cursor.execute(
            "SELECT bank FROM association_table WHERE username=?", (self.username,)
        )
        result = self.cursor.fetchall()
        banks = ""
        for bank in result:
            banks += f"{str(bank['bank'])}\n"

        return banks


class JobsFormatter(flux.util.OutputFormat):
    """
    Store a parsed version of an output format string for JobRecord objects,
    allowing the fields to iterated without modifiers, building
    a new format suitable for headers display, etc...
    """

    # mapping of legal format fields and their header names
    headings = {
        "userid": "userid",
        "username": "username",
        "jobid": "jobid",
        "t_submit": "t_submit",
        "t_run": "t_run",
        "t_inactive": "t_inactive",
        "nnodes": "nnodes",
        "resources": "resources",
        "project": "project",
        "bank": "bank",
    }

    def __init__(self, fmt, headings=None):
        """
        Parse the input format fmt with string.Formatter.
        Save off the fields and list of format tokens for later use,
        (converting None to "" in the process)

        Throws an exception if any format fields do not match the allowed
        list of headings above.

        Special case for annotations, which may be arbitrary
        creations of scheduler or user.
        """
        format_list = string.Formatter().parse(fmt)
        for _, field, _, _ in format_list:
            if field and field in self.headings:
                self.headings[field] = field
        super().__init__(fmt)

    def build_table(self, items):
        """
        Handle constructing a table of job records with the current format.

        Sort items via any sort keys as set by set_sort_keys() or
        via a ``sort:`` prefix in the supplied format.

        Args:
            items (iterable): list of items to format
        """
        # preprocess original format by processing with filter():
        newfmt = self.filter(items)
        # create new instance of the current class from filtered format:
        formatter = type(self)(newfmt, headings=self.headings)

        items = self.sort_items(items)

        output_str = f"{formatter.header()}\n"
        for item in items:
            line = formatter.format(item)
            if not line or line.isspace():
                continue
            try:
                output_str += f"{line}\n"
            except UnicodeEncodeError:
                output_str += (
                    f"{line.encode('utf-8', errors='surrogateescape').decode()}"
                )

        return output_str


class QueueFormatter(AccountingFormatter):
    """
    Subclass of AccountingFormatter that includes a custom error message in the
    case where a queue does not exist in the queue_table.
    """

    def __init__(self, cursor, queue_name):
        """
        Initialize a QueueFormatter object with a SQLite cursor.
        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
            queue_name: the name of the queue.
        """
        self.queue_name = queue_name
        super().__init__(
            cursor, error_msg=f"queue {self.queue_name} not found in queue_table"
        )
