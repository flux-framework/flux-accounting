#!/usr/bin/env python3

###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
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
import time
import ast
from unittest.mock import patch

from fluxacct.database import create as c
from fluxacct.database import info as d
from fluxacct.entities import associations as u
from fluxacct.entities import banks as b


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global conn
        global cur

        conn = sqlite3.connect(self.dbname, timeout=60)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # add banks, associations to database
        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, parent_bank="root", bank="A", shares=1)
        u.add_user(conn, username="user1", uid=50001, bank="A")

    # check parameters of config_table
    def test_01_check_config(self):
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 2419200", result)
        self.assertIn("priority_decay_half_life    | 604800", result)
        self.assertIn("decay_factor                | 0.5", result)

    def test_02_check_job_usage_per_association(self):
        result = u.view_user(conn, user="user1", job_usage=True)
        # evaluate the string as a Python list of dictionaries
        self.assertEqual(len(ast.literal_eval(result)), 4)

    # change the configuration of the bins to have a half-life period of 2 weeks
    # instead of 1 week and a usage reset period of 6 weeks instead of 4 weeks, which
    # will result in a total of 3 bins per-association
    @patch("builtins.input", return_value="y")
    def test_03_edit_configs_1(self, mock_input):
        d.edit_config(conn, ["priority_usage_reset_period=42d"])
        d.edit_config(conn, ["priority_decay_half_life=14d"])
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 3628800", result)
        self.assertIn("priority_decay_half_life    | 1209600", result)

    def test_04_reconfigure_bins_1(self):
        result = u.view_user(conn, user="user1", job_usage=True)
        # evaluate the string as a Python list of dictionaries
        self.assertEqual(len(ast.literal_eval(result)), 3)

    # change the configuration of the bins to have a half-life period of 8 hours and
    # a usage reset period of 16 hours
    @patch("builtins.input", return_value="y")
    def test_05_edit_configs_2(self, mock_input):
        d.edit_config(conn, ["priority_usage_reset_period=16h"])
        d.edit_config(conn, ["priority_decay_half_life=8h"])
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 57600", result)
        self.assertIn("priority_decay_half_life    | 28800", result)

    def test_06_reconfigure_bins_2(self):
        result = u.view_user(conn, user="user1", job_usage=True)
        # evaluate the string as a Python list of dictionaries
        self.assertEqual(len(ast.literal_eval(result)), 2)

    # change the configuration of the bins to have a half-life period of 15 minutes and
    # a usage reset period of 1 hour
    @patch("builtins.input", return_value="y")
    def test_07_edit_configs_3(self, mock_input):
        d.edit_config(conn, ["priority_usage_reset_period=1h"])
        d.edit_config(conn, ["priority_decay_half_life=15m"])
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 3600", result)
        self.assertIn("priority_decay_half_life    | 900", result)

    def test_08_reconfigure_bins_3(self):
        result = u.view_user(conn, user="user1", job_usage=True)
        # evaluate the string as a Python list of dictionaries
        self.assertEqual(len(ast.literal_eval(result)), 4)

    def test_09_reconfigure_bins_rollback(self):
        def fetch_rows(query):
            return [tuple(row) for row in cur.execute(query).fetchall()]

        config_query = (
            "SELECT key, value FROM config_table "
            "WHERE key IN ('priority_usage_reset_period', "
            "'priority_decay_half_life', 'reconfigure_time') ORDER BY key"
        )
        bins_query = (
            "SELECT username, userid, bank, period, value "
            "FROM job_usage_per_association_table ORDER BY username, bank, period"
        )
        last_job_timestamps_query = (
            "SELECT username, userid, bank, last_job_timestamp "
            "FROM job_usage_factor_table ORDER BY username, bank"
        )
        half_life_periods_query = (
            "SELECT cluster, end_half_life_period FROM t_half_life_period_table "
            "ORDER BY cluster"
        )
        config_before = fetch_rows(config_query)
        bins_before = fetch_rows(bins_query)
        last_job_timestamps_before = fetch_rows(last_job_timestamps_query)
        half_life_periods_before = fetch_rows(half_life_periods_query)

        reconfigure_usage_bins = d.reconfigure_usage_bins

        def reconfigure_then_fail(connection):
            reconfigure_usage_bins(connection)
            raise RuntimeError("failure after reconfiguring usage bins")

        with patch.object(
            d, "reconfigure_usage_bins", side_effect=reconfigure_then_fail
        ):
            with self.assertRaisesRegex(RuntimeError, "failure after reconfiguring"):
                d.edit_config(conn, ["priority_usage_reset_period=2h"])

        self.assertEqual(fetch_rows(config_query), config_before)
        self.assertEqual(fetch_rows(bins_query), bins_before)
        self.assertEqual(
            fetch_rows(last_job_timestamps_query), last_job_timestamps_before
        )
        self.assertEqual(fetch_rows(half_life_periods_query), half_life_periods_before)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove(self.dbname)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
