#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import shutil
import sys


class RenderBarGraph:
    """A class for displaying a horizontal bar graph."""

    def __init__(self, conn, query, query_params=(), bar_char="█", fallback_char="#"):
        """
        Initialize the graph renderer.

        Parameters:
            conn: A SQLite Connection object.
            query: The query to the flux-accounting DB to actually fetch the data used
                in the graph.
            query_params: Any parameters specified for the SQLite query.
            bar_char: The primary character to draw the bars (default: block char).
            fallback_char: A fallback ASCII character if primary char can't be encoded in
                the terminal.
        """
        self.conn = conn
        self.bar_char = bar_char
        self.fallback_char = fallback_char
        self.query = query
        self.query_params = query_params

    def fetch_rows(self):
        cur = self.conn.cursor()
        if self.query_params != ():
            cur.execute(self.query, self.query_params)
        else:
            cur.execute(self.query)
        return cur.fetchall()

    def make_label(self, row):
        """Return string label for a row; override in subclasses."""
        raise NotImplementedError

    def _bar_char(self):
        """Return the appropriate bar character based on terminal encoding support."""
        encoding = sys.stdout.encoding or "utf-8"
        try:
            self.bar_char.encode(encoding)
            return self.bar_char
        except (UnicodeEncodeError, TypeError):
            return self.fallback_char

    def draw(self):
        rows = self.fetch_rows()
        if not rows:
            return "no data to display"

        labels = [self.make_label(row) for row in rows]
        # last column will be the numerical value to display
        values = [row[-1] for row in rows]

        term_width = shutil.get_terminal_size().columns
        # max width for the labels on y-axis
        max_label = max(len(lbl) for lbl in labels)
        reserved = max_label + 10 + max(len(f"{v:.2f}") for v in values)
        max_bar = max(term_width - reserved, 10)
        scale = 0 if max(values) == 0 else max_bar / max(values)

        char = self._bar_char()
        lines = []
        for lbl, val in zip(labels, values):
            bar_len = int(val * scale)
            bar_character = char * bar_len
            lines.append(f"{lbl:<{max_label}} | {bar_character:<{max_bar}} {val: .2f}")
        return "\n".join(lines)


class AssociationUsageGraph(RenderBarGraph):
    def __init__(self, conn, limit, bar_char="█", fallback_char="#"):
        """
        A subclass of RenderBarGraph to display job_usage data from the
        association_table. Order the data in descending order by job_usage. Allow for a
        configurable amount of data to be displayed in the graph.

        Args:
            conn: The SQLite Connection object.
            limit: The max number of rows to display on the graph.
            bar_char: The character used to dsiplay the horizontal bar on the graph.
            fallback_char: A fallback character used to display the horizontal bar on
                the graph.
        """
        self.conn = conn
        self.limit = limit
        self.bar_char = bar_char
        self.fallback_char = fallback_char
        # the following attributes are manually set here to query the flux-accounting
        # DB using the fetch_rows() method in the RenderBarGraph class
        self.query = (
            "SELECT username,bank,job_usage FROM association_table "
            "ORDER BY job_usage DESC LIMIT ?"
        )
        self.query_params = (self.limit,)
        super().__init__(conn, self.query, self.query_params)

    def make_label(self, row):
        return f"{row['username']} / {row['bank']}"


class BankUsageGraph(RenderBarGraph):
    def __init__(self, conn, limit, bar_char="█", fallback_char="#"):
        """
        A subclass of RenderBarGraph to display job_usage data from the
        bank_table. Order the data in descending order by job_usage. Allow for a
        configurable amount of data to be displayed in the graph.

        Args:
            conn: The SQLite Connection object.
            limit: The max number of rows to display on the graph.
            bar_char: The character used to dsiplay the horizontal bar on the graph.
            fallback_char: A fallback character used to display the horizontal bar on
                the graph.
        """
        self.conn = conn
        self.limit = limit
        self.bar_char = bar_char
        self.fallback_char = fallback_char
        self.query = (
            "SELECT bank,job_usage FROM bank_table WHERE parent_bank != '' "
            "ORDER BY job_usage DESC LIMIT ?"
        )
        self.query_params = (self.limit,)
        super().__init__(conn, self.query, self.query_params)

    def make_label(self, row):
        return row["bank"]


def show_usage(conn, table, limit=10):
    """
    Create a horizontal bar graph for displaying job usage data for either associations
    or banks.

    Args:
        conn: The SQLite Connection object.
        table: The name of the table to pull job usage data from.
        limit: The max number of rows to display on the graph.
    """
    if table == "associations":
        return AssociationUsageGraph(conn, limit=limit).draw()

    return BankUsageGraph(conn, limit=limit).draw()
