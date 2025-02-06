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
import unittest
import os
import sqlite3
import textwrap

import fluxacct.accounting
from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import formatter as fmt


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("test_view_associations.db")
        global conn
        global cur

        conn = sqlite3.connect("test_view_associations.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    # add some associations, initialize formatter
    def test_AccountingFormatter_with_associations(self):
        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, bank="A", shares=1, parent_bank="root")
        u.add_user(conn, username="user1", bank="A")

        cur.execute("SELECT * FROM association_table")
        formatter = fmt.AssociationFormatter(cur, "user1")

        self.assertIsInstance(formatter, fmt.AssociationFormatter)

    def test_default_columns_association_table(self):
        cur.execute("PRAGMA table_info (association_table)")
        columns = cur.fetchall()
        association_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.ASSOCIATION_TABLE, association_table)

    def test_view_association_noexist(self):
        with self.assertRaises(ValueError):
            u.view_user(conn, user="foo")

    # test JSON output for viewing an association
    def test_view_association(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "active": 1,
            "username": "user1",
            "bank": "A",
            "shares": 1
          }
        ]
        """
        )
        test = u.view_user(
            conn, user="user1", cols=["active", "username", "bank", "shares"]
        )
        self.assertEqual(expected.strip(), test.strip())

    def test_view_association_table(self):
        expected = textwrap.dedent(
            """\
        active | username | bank | shares
        -------+----------+------+-------
        1      | user1    | A    | 1  
        """
        )
        test = u.view_user(
            conn,
            user="user1",
            parsable=True,
            cols=["active", "username", "bank", "shares"],
        )
        self.assertEqual(expected.strip(), test.strip())

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("test_view_associations.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
