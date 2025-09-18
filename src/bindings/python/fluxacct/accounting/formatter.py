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
import fluxacct.accounting.util as u


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
        return [tuple(u.format_value(v) for v in row) for row in self.rows]

    def as_table(self):
        """
        Format a SQL query in table format.

        Returns:
            table: the data from the query formatted as a table.
        """
        # fetch column names and determine the width of each column
        col_names = [description[0] for description in self.cursor.description]
        col_widths = [
            max(
                len(str(u.format_value(value)))
                for value in [col] + [row[i] for row in self.rows]
            )
            for i, col in enumerate(col_names)
        ]

        # format a row of data
        def format_row(row):
            return " | ".join(
                [
                    f"{str(u.format_value(value)).ljust(col_widths[i])}"
                    for i, value in enumerate(row)
                ]
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
            {col_names[i]: u.format_value(row[i]) for i in range(len(col_names))}
            for row in self.rows
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

    def _iterate_hierarchy(self, bank, fmt_bank, fmt_user, indent="", concise=False):
        """
        Internal generator to traverse banks and yield formatted lines.
        """
        # fetch direct sub banks
        self.cursor.execute(
            "SELECT bank,shares,job_usage FROM bank_table WHERE parent_bank=?", (bank,)
        )
        sub_banks = self.cursor.fetchall()
        if not sub_banks:
            # leaf bank: list users
            select_stmt = (
                "SELECT username,shares,job_usage,fairshare FROM association_table "
                "WHERE bank=?"
            )
            if concise:
                # only display associations that have a job usage value greater than 0
                select_stmt += " AND job_usage > 0"
            self.cursor.execute(
                select_stmt,
                (bank,),
            )
            for user in self.cursor.fetchall():
                yield fmt_user(bank, user, indent)
        else:
            for sub_bank in sub_banks:
                yield fmt_bank(sub_bank, indent)
                yield from self._iterate_hierarchy(
                    sub_bank["bank"], fmt_bank, fmt_user, indent + " ", concise
                )

    def as_tree(self, concise):
        """
        Format the flux-accounting bank hierarchy in tree format. The bank passed
        into the query will serve as the root of the tree.

        Returns:
            hierarchy: the hierarchy of banks in bank_table with the passed-in bank
                as the root of the tree.
        """
        # header for hierarchy string
        header = (
            "Bank".ljust(20)
            + "Username".rjust(20)
            + "RawShares".rjust(20)
            + "RawUsage".rjust(20)
            + "Fairshare".rjust(20)
        )

        # the root line of the hierarchy will not have an indent
        root_bank = self.rows[0]
        root_line = (
            str(root_bank["bank"]).ljust(20)
            + "".rjust(20)
            + str(root_bank["shares"]).rjust(20)
            + str(round(root_bank["job_usage"], 2)).rjust(20)
        )

        def fmt_bank(row, indent):
            prefix = indent + " "
            return (
                prefix
                + str(row["bank"]).ljust(20)
                + "".rjust(20 - (len(prefix)))
                + str(row["shares"]).rjust(20)
                + str(row["job_usage"]).rjust(20)
            )

        def fmt_user(bank, user, indent):
            prefix = indent + " "
            return (
                prefix
                + bank.ljust(20)
                + str(user["username"]).rjust(20 - len(prefix))
                + str(user["shares"]).rjust(20)
                + str(user["job_usage"]).rjust(20)
                + str(user["fairshare"]).rjust(20)
            )

        lines = [header, root_line]
        lines.extend(
            self._iterate_hierarchy(root_bank["bank"], fmt_bank, fmt_user, "", concise)
        )
        return "\n".join(lines) + "\n"

    def as_parsable_tree(self, bank, concise):
        """
        Format the flux-accounting bank hierarchy in a parsable tree format starting with
        the bank passed in serving as the root of the tree. Delimit the items in each row
        with a pipe ('|') character.

        Returns:
            hierarchy: a string representing the hierarchy of banks in the
                flux-accounting DB as a parsable tree.
        """
        # header for hierarchy string
        header = "Bank|Username|RawShares|RawUsage|Fairshare"

        # the root line of the hierarchy will not have an indent
        root_bank = self.rows[0]
        root_line = (
            f"{root_bank['bank']}||{root_bank['shares']}|"
            f"{str(round(root_bank['job_usage'], 2))}"
        )

        def fmt_bank(row, indent):
            prefix = indent + " "
            return f"{prefix}{row['bank']}||{row['shares']}|{row['job_usage']}"

        def fmt_user(bank, user, indent):
            prefix = indent + " "
            return (
                f"{prefix}{bank}|{user['username']}|{user['shares']}|"
                f"{user['job_usage']}|{user['fairshare']}"
            )

        lines = [header, root_line]
        lines.extend(
            self._iterate_hierarchy(root_bank["bank"], fmt_bank, fmt_user, "", concise)
        )
        return "\n".join(lines) + "\n"

    def with_users(self, bank, concise):
        """
        Print basic information for all of the users under a given bank in table
        format.

        Returns:
            info: the information for both the bank and basic information for all
                users under that bank.
        """
        try:
            info = self.as_table()

            select_stmt = (
                "SELECT username,default_bank,shares,job_usage,fairshare "
                "FROM association_table WHERE bank=?"
            )
            if concise:
                select_stmt += " AND job_usage > 0"
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
        "requested_duration": "requested_duration",
        "actual_duration": "actual_duration",
        "duration_delta": "duration_delta",
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


class ProjectFormatter(AccountingFormatter):
    """
    Subclass of AccountingFormatter that includes a custom error message in the
    case where a project does not exist in the project_table.
    """

    def __init__(self, cursor, project_name):
        """
        Initialize a ProjectFormatter object with a SQLite cursor.
        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
            project: the name of the project.
        """
        self.project_name = project_name
        super().__init__(
            cursor, error_msg=f"project {self.project_name} not found in project_table"
        )


class PriorityFactorFormatter(AccountingFormatter):
    """
    Subclass of AccountingFormatter that includes a custom error message in the
    case where a factor does not exist in the priority_factor_weight_table.
    """

    def __init__(self, cursor, factor):
        """
        Initialize a PriorityFactorFormatter object with a SQLite cursor.
        Args:
            cursor: a SQLite Cursor object that has the results of a SQL query.
            factor: the name of the priority factor.
        """
        self.factor = factor
        super().__init__(
            cursor,
            error_msg=f"factor {self.factor} not found in priority_factor_weight_table",
        )
