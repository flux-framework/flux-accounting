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
import unittest
import os
import sqlite3
import textwrap

from fluxacct.accounting import create_db as c
from fluxacct.accounting import priorities as prio


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("FluxAccountingPriorities.db")
        global conn
        global cur

        conn = sqlite3.connect("FluxAccountingPriorities.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    # view the information about a particular priority factor weight
    def test_01_view_priority_factor_weight_success(self):
        test = prio.view_factor(conn, "fairshare")
        self.assertIn("fairshare | 100000", test)

    # trying to pass a factor that does not exist will raise a ValueError
    def test_02_view_priority_factor_weight_failure(self):
        with self.assertRaises(ValueError):
            prio.view_factor(conn, "foo")

    # edit the weight for a particular priority factor
    def test_03_edit_priority_factor_weight_success(self):
        prio.edit_factor(conn, factor="fairshare", weight=999)
        test = prio.view_factor(conn, "fairshare", json_fmt=True)
        self.assertIn('"weight": 999', test)

    # trying to edit a factor that does not exist will raise a ValueError
    def test_04_edit_priority_factor_weight_failure(self):
        with self.assertRaises(ValueError):
            prio.edit_factor(conn, factor="foo", weight=999)

    # list all of the factors in the table
    def test_05_list_factors_table(self):
        test = prio.list_factors(conn)
        self.assertIn("fairshare | 999", test)
        self.assertIn("queue     | 10000", test)
        self.assertIn("bank      | 0", test)

    # list all of the factors in the table in JSON format
    def test_06_list_factors_json(self):
        test = prio.list_factors(conn, json_fmt=True)
        self.assertIn('"factor": "fairshare"', test)
        self.assertIn('"weight": 999', test)
        self.assertIn('"factor": "queue"', test)
        self.assertIn('"weight": 10000', test)
        self.assertIn('"factor": "bank"', test)
        self.assertIn('"weight": 0', test)

    # list all of the factors in the table with no weight
    def test_07_list_factors_custom(self):
        test = prio.list_factors(conn, cols=["factor"])
        expected = textwrap.dedent(
            """\
        factor   
        ---------
        bank     
        fairshare
        queue    
        urgency
        """
        )
        self.assertEqual(expected.strip(), test.strip())

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("FluxAccountingPriorities.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
