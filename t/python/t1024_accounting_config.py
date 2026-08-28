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

from fluxacct.accounting import create_db as c
from fluxacct.accounting import util
from fluxacct.accounting.config import AccountingConfig


def write_toml(contents):
    filename = f"TestConfig_{round(time.time())}.toml"
    with open(filename, "w") as toml_file:
        toml_file.write(contents)
    return filename


class TestAccountingConfig(unittest.TestCase):
    # the default configuration matches the historical hard-coded values
    def test_01_default_config(self):
        conf = AccountingConfig()
        self.assertEqual(conf["usage"]["reset-period"], 2419200)
        self.assertEqual(conf["usage"]["decay-half-life"], 604800)
        self.assertEqual(conf["usage"]["decay-factor"], 0.5)
        self.assertEqual(conf["usage"]["calculation-mode"], "periodic")
        self.assertEqual(
            conf["usage"]["weights"], {"node": 1.0, "core": 0.0, "gpu": 0.0}
        )
        self.assertEqual(conf["queues"]["deny-unknown"], False)
        self.assertEqual(
            conf["priority"]["factors"],
            {"fairshare": 100000, "queue": 10000, "bank": 0, "urgency": 1000},
        )

    # keys from a TOML file override defaults; missing keys keep defaults
    def test_02_load_config_file(self):
        filename = write_toml(
            "[accounting.usage]\n"
            'decay-half-life = "14d"\n'
            "decay-factor = 0.25\n"
            "[accounting.usage.weights]\n"
            "core = 1.0\n"
            "[accounting.priority.factors]\n"
            "fairshare = 50000\n"
        )
        conf = AccountingConfig(filename)
        os.remove(filename)
        self.assertEqual(conf["usage"]["decay-half-life"], 1209600)
        self.assertEqual(conf["usage"]["reset-period"], 2419200)
        self.assertEqual(conf["usage"]["decay-factor"], 0.25)
        self.assertEqual(
            conf["usage"]["weights"], {"node": 1.0, "core": 1.0, "gpu": 0.0}
        )
        self.assertEqual(conf["priority"]["factors"]["fairshare"], 50000)
        self.assertEqual(conf["priority"]["factors"]["queue"], 10000)

    # durations can also be expressed as a number of seconds
    def test_03_duration_in_seconds(self):
        filename = write_toml("[accounting.usage]\ndecay-half-life = 86400\n")
        conf = AccountingConfig(filename)
        os.remove(filename)
        self.assertEqual(conf["usage"]["decay-half-life"], 86400)

    # an unknown section in [accounting] raises a ValueError
    def test_04_unknown_section(self):
        filename = write_toml("[accounting.foo]\nbar = 1\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an unknown key in a section raises a ValueError
    def test_05_unknown_key(self):
        filename = write_toml("[accounting.usage]\nfoo = 1\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # a file without an [accounting] section raises a ValueError
    def test_06_missing_accounting_section(self):
        filename = write_toml("[foo]\nbar = 1\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an unknown resource type in usage.weights raises a ValueError
    def test_07_unknown_resource_type(self):
        filename = write_toml("[accounting.usage.weights]\nquantum = 5.0\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an unknown priority factor raises a ValueError
    def test_08_unknown_priority_factor(self):
        filename = write_toml("[accounting.priority.factors]\nfoo = 1\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # a non-integer priority factor weight raises a ValueError
    def test_09_bad_factor_weight(self):
        filename = write_toml('[accounting.priority.factors]\nfairshare = "high"\n')
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an out-of-range decay factor raises a ValueError
    def test_10_bad_decay_factor(self):
        filename = write_toml("[accounting.usage]\ndecay-factor = 1.5\n")
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an invalid duration raises a ValueError
    def test_11_bad_duration(self):
        filename = write_toml('[accounting.usage]\ndecay-half-life = "foo"\n')
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)

    # an infinite or non-positive duration raises a ValueError
    def test_12_out_of_range_duration(self):
        for value in ('"infinity"', "0"):
            filename = write_toml(f"[accounting.usage]\ndecay-half-life = {value}\n")
            with self.assertRaises(ValueError):
                AccountingConfig(filename)
            os.remove(filename)

    # a file that is not valid TOML raises a ValueError
    def test_13_invalid_toml(self):
        filename = write_toml("this is not valid toml\n")
        with self.assertRaises(ValueError):
            util.load_toml(filename)
        os.remove(filename)

    # a nonexistent path raises an OSError
    def test_14_nonexistent_file(self):
        with self.assertRaises(OSError):
            AccountingConfig("nonexistent_config.toml")

    # creating a DB with a config file seeds the configured values
    def test_15_create_db_with_config(self):
        filename = write_toml(
            "[accounting.usage]\n"
            'decay-half-life = "14d"\n'
            "decay-factor = 0.8\n"
            'calculation-mode = "continuous"\n'
            "[accounting.usage.weights]\n"
            "core = 1.0\n"
            "[accounting.priority.factors]\n"
            "fairshare = 999\n"
            "[accounting.queues]\n"
            "deny-unknown = true\n"
        )
        dbname = f"TestDB_{round(time.time())}.db"
        c.create_db(dbname, config_path=filename)
        conn = sqlite3.connect(dbname)
        config_table = dict(conn.execute("SELECT key, value FROM config_table"))
        factor_weights = dict(
            conn.execute("SELECT factor, weight FROM priority_factor_weight_table")
        )
        conn.close()
        os.remove(dbname)
        os.remove(filename)
        self.assertEqual(config_table["priority_decay_half_life"], "1209600")
        self.assertEqual(config_table["priority_usage_reset_period"], "2419200")
        self.assertEqual(config_table["decay_factor"], "0.8")
        self.assertEqual(config_table["core_weight"], "1.0")
        self.assertEqual(config_table["node_weight"], "1.0")
        self.assertEqual(config_table["deny_unknown_queues"], "true")
        self.assertEqual(config_table["usage_calculation_mode"], "continuous")
        self.assertEqual(factor_weights["fairshare"], 999)
        self.assertEqual(factor_weights["queue"], 10000)

    # explicitly passed-in arguments take precedence over the config file
    def test_16_create_db_arg_precedence(self):
        filename = write_toml('[accounting.usage]\ndecay-half-life = "14d"\n')
        dbname = f"TestDB_{round(time.time())}.db"
        c.create_db(dbname, priority_decay_half_life="1d", config_path=filename)
        conn = sqlite3.connect(dbname)
        config_table = dict(conn.execute("SELECT key, value FROM config_table"))
        conn.close()
        os.remove(dbname)
        os.remove(filename)
        self.assertEqual(float(config_table["priority_decay_half_life"]), 86400.0)

    # calculation-mode accepts 'continuous'; an unknown mode raises a ValueError
    def test_17_calculation_mode(self):
        filename = write_toml('[accounting.usage]\ncalculation-mode = "continuous"\n')
        conf = AccountingConfig(filename)
        os.remove(filename)
        self.assertEqual(conf["usage"]["calculation-mode"], "continuous")

        filename = write_toml('[accounting.usage]\ncalculation-mode = "bogus"\n')
        with self.assertRaises(ValueError):
            AccountingConfig(filename)
        os.remove(filename)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
