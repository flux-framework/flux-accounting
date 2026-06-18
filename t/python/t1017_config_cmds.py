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
from unittest.mock import patch

from fluxacct.accounting import create_db as c
from fluxacct.accounting import db_info_subcommands as d


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

    # add a key-value pair to config_table
    def test_01_add_config(self):
        d.add_config(conn, key_value_string="foo=bar")
        test = cur.execute("SELECT * FROM config_table WHERE key='foo'").fetchone()
        self.assertEqual(test["key"], "foo")
        self.assertEqual(test["value"], "bar")

    # trying to add an already-existing key will raise a sqlite3.IntegrityError
    def test_02_add_config_duplicate_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            d.add_config(conn, key_value_string="priority_decay_half_life=foo")

    # edit a key-value pair in config_table
    def test_03_edit_config(self):
        d.edit_config(conn, key_value_strings=["foo=baz"])
        test = cur.execute("SELECT value FROM config_table WHERE key='foo'").fetchone()
        self.assertEqual(test["value"], "baz")

    # trying to set PriorityUsageResetPeriod to a non-integer will raise a ValueError
    def test_04_edit_priority_usage_reset_period_bad(self):
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["priority_usage_reset_period=foo"])

    # successfully edit PriorityUsageResetPeriod
    @patch("builtins.input", return_value="y")
    def test_05_edit_priority_usage_reset_period_success(self, mock_input):
        d.edit_config(conn, key_value_strings=["priority_usage_reset_period=1234"])
        test = cur.execute(
            "SELECT value FROM config_table WHERE key='priority_usage_reset_period'"
        ).fetchone()
        self.assertEqual(test["value"], "1234.0")

    # edit PriorityUsageResetPeriod using a Flux Standard Duration value
    @patch("builtins.input", return_value="y")
    def test_06_edit_priority_usage_reset_period_fsd_success(self, mock_input):
        d.edit_config(conn, key_value_strings=["priority_usage_reset_period=1d"])
        test = cur.execute(
            "SELECT value FROM config_table WHERE key='priority_usage_reset_period'"
        ).fetchone()
        self.assertEqual(test["value"], "86400.0")

    # trying to set PriorityDecayHalfLife to a non-integer will raise a ValueError
    def test_07_edit_priority_decay_half_life_bad(self):
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["priority_decay_half_life=foo"])

    # successfully edit PriorityDecayHalfLife
    @patch("builtins.input", return_value="y")
    def test_08_edit_priority_decay_half_life_success(self, mock_input):
        d.edit_config(conn, key_value_strings=["priority_decay_half_life=1234"])
        test = cur.execute(
            "SELECT value FROM config_table WHERE key='priority_decay_half_life'"
        ).fetchone()
        self.assertEqual(test["value"], "1234.0")

    # edit PriorityDecayHalfLife using a Flux Standard Duration value
    @patch("builtins.input", return_value="y")
    def test_09_edit_priority_decay_half_life_fsd_success(self, mock_input):
        d.edit_config(conn, key_value_strings=["priority_decay_half_life=1h"])
        test = cur.execute(
            "SELECT value FROM config_table WHERE key='priority_decay_half_life'"
        ).fetchone()
        self.assertEqual(test["value"], "3600.0")

    # trying to set decay_factor to a non-float will raise a ValueError
    def test_10_edit_decay_factor_bad_1(self):
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["decay_factor=foo"])

    # trying to set decay_factor to a float not between 0 and 1 will raise a ValueError
    def test_11_edit_decay_factor_bad_2(self):
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["decay_factor=-0.1"])
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["decay_factor=1.1"])

    # successfully edit decay_factor
    @patch("builtins.input", return_value="y")
    def test_12_edit_decay_factor_success(self, mock_input):
        d.edit_config(conn, key_value_strings=["decay_factor=0.9"])
        test = cur.execute(
            "SELECT value FROM config_table WHERE key='decay_factor'"
        ).fetchone()
        self.assertEqual(test["value"], "0.9")

    # remove a key-value pair from config_table
    def test_13_delete_config(self):
        d.add_config(conn, key_value_string="hello=world")
        test = cur.execute("SELECT * FROM config_table WHERE key='hello'").fetchone()
        self.assertEqual(test["value"], "world")

        d.delete_config(conn, key="hello")
        with self.assertRaises(ValueError):
            d.view_config(conn, key="hello")

    # trying to remove PriorityUsageResetPeriod will raise a ValueError
    def test_14_delete_priority_usage_reset_period(self):
        with self.assertRaises(ValueError):
            d.delete_config(conn, key="priority_usage_reset_period")

    # trying to remove PriorityDecayHalfLife will raise a ValueError
    def test_15_delete_priority_decay_half_life(self):
        with self.assertRaises(ValueError):
            d.delete_config(conn, key="priority_decay_half_life")

    # trying to remove decay_factor will raise a ValueError
    def test_16_delete_decay_factor(self):
        with self.assertRaises(ValueError):
            d.delete_config(conn, key="decay_factor")

    # trying to view a key-value pair that does not exist will raise a ValueError
    def test_17_view_config_bad(self):
        with self.assertRaises(ValueError):
            d.view_config(conn, key="noexist")

    # view information about a key-value pair
    def test_18_view_config(self):
        test = d.view_config(conn, key="priority_usage_reset_period")
        self.assertIn("priority_usage_reset_period", test)
        self.assertIn("86400.0", test)

    # view information about a key-value pair in JSON format
    def test_19_view_config_json(self):
        test = d.view_config(conn, key="priority_usage_reset_period", json_fmt=True)
        self.assertIn('"key": "priority_usage_reset_period"', test)
        self.assertIn('"value": "86400.0"', test)

    def test_20_view_config_format_string(self):
        test = d.view_config(
            conn, key="priority_usage_reset_period", format_string="{key}||{value}"
        )
        self.assertIn("priority_usage_reset_period||86400.0", test)

    def test_21_list_configs(self):
        test = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 86400.0", test)
        self.assertIn("priority_decay_half_life    | 3600.0", test)
        self.assertIn("decay_factor                | 0.9", test)

    def test_22_list_configs_json(self):
        test = d.list_configs(conn, json_fmt=True)
        self.assertIn('"key": "priority_usage_reset_period"', test)
        self.assertIn('"value": "86400.0"', test)
        self.assertIn('"key": "priority_decay_half_life"', test)
        self.assertIn('"value": "3600.0"', test)
        self.assertIn('"key": "decay_factor"', test)
        self.assertIn('"value": "0.9"', test)

    def test_23_list_configs_format_string(self):
        test = d.list_configs(conn, format_string="{key} -> {value}")
        self.assertIn("priority_usage_reset_period -> 86400.0", test)
        self.assertIn("priority_decay_half_life -> 3600.0", test)
        self.assertIn("decay_factor -> 0.9", test)

    def test_24_add_config_bad_format(self):
        with self.assertRaises(ValueError):
            d.add_config(conn, key_value_string="bad=format=foo")

    def test_25_add_config_bad_format_2(self):
        with self.assertRaises(ValueError):
            d.add_config(conn, key_value_string="foobar")

    def test_26_edit_config_nonexistent_key(self):
        with self.assertRaises(ValueError):
            d.edit_config(conn, key_value_strings=["i_dont_exist=foo"])

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
