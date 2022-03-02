#!/usr/bin/env python3

###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
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

from fluxacct.accounting import create_db as c
from fluxacct.accounting import plugin_factor_subcommands as p


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("TestPluginFactorSubcommands.db")
        global acct_conn
        global cur

        acct_conn = sqlite3.connect("TestPluginFactorSubcommands.db")
        cur = acct_conn.cursor()

    # edit the weight for the fairshare factor
    def test_01_edit_fairshare_factor_successfully(self):
        p.edit_factor(acct_conn, factor="fairshare", weight=1500)
        cur.execute("SELECT weight FROM plugin_factor_table WHERE factor='fairshare'")
        row = cur.fetchone()

        self.assertEqual(row[0], 1500)

    # edit the weight for the queue factor
    def test_02_edit_queue_factor_successfully(self):
        p.edit_factor(acct_conn, factor="queue", weight=200)
        cur.execute("SELECT weight FROM plugin_factor_table WHERE factor='queue'")
        row = cur.fetchone()

        self.assertEqual(row[0], 200)

    # try to edit a factor with a bad type
    def test_03_edit_factor_bad_type(self):
        with self.assertRaises(ValueError):
            p.edit_factor(acct_conn, factor="fairshare", weight="foo")

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestPluginFactorSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
