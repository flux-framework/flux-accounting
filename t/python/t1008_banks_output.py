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
from fluxacct.accounting import formatter as fmt


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("test_view_banks.db")
        global conn
        global cur

        conn = sqlite3.connect("test_view_banks.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    # add some banks, initialize formatter
    def test_AccountingFormatter_with_banks(self):
        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, bank="A", shares=1, parent_bank="root")

        cur.execute("SELECT * FROM bank_table")
        formatter = fmt.AccountingFormatter(cur)

        self.assertIsInstance(formatter, fmt.AccountingFormatter)

    def test_default_columns_bank_table(self):
        cur.execute("PRAGMA table_info (bank_table)")
        columns = cur.fetchall()
        bank_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.BANK_TABLE, bank_table)

    # test JSON output for listing all banks
    def test_list_banks_default(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root",
            "active": 1,
            "parent_bank": "",
            "shares": 1,
            "job_usage": 0.0,
            "priority": 0.0
          },
          {
            "bank_id": 2,
            "bank": "A",
            "active": 1,
            "parent_bank": "root",
            "shares": 1,
            "job_usage": 0.0,
            "priority": 0.0
          }
        ]
        """
        )
        test = b.list_banks(conn, json_fmt=True)
        self.assertEqual(expected.strip(), test.strip())

    # test JSON output with custom columns
    def test_list_banks_custom_one(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1
          },
          {
            "bank_id": 2
          }
        ]
        """
        )
        test = b.list_banks(conn, json_fmt=True, cols=["bank_id"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_custom_two(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root"
          },
          {
            "bank_id": 2,
            "bank": "A"
          }
        ]
        """
        )
        test = b.list_banks(conn, json_fmt=True, cols=["bank_id", "bank"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_custom_three(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root",
            "active": 1
          },
          {
            "bank_id": 2,
            "bank": "A",
            "active": 1
          }
        ]
        """
        )
        test = b.list_banks(conn, json_fmt=True, cols=["bank_id", "bank", "active"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_custom_four(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root",
            "active": 1,
            "parent_bank": ""
          },
          {
            "bank_id": 2,
            "bank": "A",
            "active": 1,
            "parent_bank": "root"
          }
        ]
        """
        )
        test = b.list_banks(
            conn, json_fmt=True, cols=["bank_id", "bank", "active", "parent_bank"]
        )
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_custom_five(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root",
            "active": 1,
            "parent_bank": "",
            "shares": 1
          },
          {
            "bank_id": 2,
            "bank": "A",
            "active": 1,
            "parent_bank": "root",
            "shares": 1
          }
        ]
        """
        )
        test = b.list_banks(
            conn,
            json_fmt=True,
            cols=["bank_id", "bank", "active", "parent_bank", "shares"],
        )
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_custom_six(self):
        expected = textwrap.dedent(
            """\
        [
          {
            "bank_id": 1,
            "bank": "root",
            "active": 1,
            "parent_bank": "",
            "shares": 1,
            "job_usage": 0.0
          },
          {
            "bank_id": 2,
            "bank": "A",
            "active": 1,
            "parent_bank": "root",
            "shares": 1,
            "job_usage": 0.0
          }
        ]
        """
        )
        test = b.list_banks(
            conn,
            json_fmt=True,
            cols=["bank_id", "bank", "active", "parent_bank", "shares", "job_usage"],
        )
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_default(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank | active | parent_bank | shares | job_usage | priority
        --------+------+--------+-------------+--------+-----------+---------
        1       | root | 1      |             | 1      | 0.0       | 0.0     
        2       | A    | 1      | root        | 1      | 0.0       | 0.0       
        """
        )
        test = b.list_banks(conn)
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_one(self):
        expected = textwrap.dedent(
            """\
        bank_id
        -------
        1      
        2            
        """
        )
        test = b.list_banks(conn, cols=["bank_id"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_two(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank
        --------+-----
        1       | root
        2       | A      
        """
        )
        test = b.list_banks(conn, cols=["bank_id", "bank"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_three(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank | active
        --------+------+-------
        1       | root | 1     
        2       | A    | 1     
        """
        )
        test = b.list_banks(conn, cols=["bank_id", "bank", "active"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_four(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank | active | parent_bank
        --------+------+--------+------------
        1       | root | 1      |            
        2       | A    | 1      | root
        """
        )
        test = b.list_banks(conn, cols=["bank_id", "bank", "active", "parent_bank"])
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_five(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank | active | parent_bank | shares
        --------+------+--------+-------------+-------
        1       | root | 1      |             | 1     
        2       | A    | 1      | root        | 1
        """
        )
        test = b.list_banks(
            conn,
            cols=["bank_id", "bank", "active", "parent_bank", "shares"],
        )
        self.assertEqual(expected.strip(), test.strip())

    def test_list_banks_table_custom_five(self):
        expected = textwrap.dedent(
            """\
        bank_id | bank | active | parent_bank | shares | job_usage
        --------+------+--------+-------------+--------+----------
        1       | root | 1      |             | 1      | 0.0      
        2       | A    | 1      | root        | 1      | 0.0
        """
        )
        test = b.list_banks(
            conn,
            cols=["bank_id", "bank", "active", "parent_bank", "shares", "job_usage"],
        )
        self.assertEqual(expected.strip(), test.strip())

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("test_view_banks.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
