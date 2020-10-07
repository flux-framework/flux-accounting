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

from accounting import accounting_cli_functions as aclif
from accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("FluxAccounting.db")
        global acct_conn
        global jobs_conn
        acct_conn = sqlite3.connect("FluxAccounting.db")

    # add a valid user to association_table
    def test_01_add_valid_user(self):
        aclif.add_user(
            acct_conn,
            username="fluxuser",
            admin_level="1",
            bank="acct",
            shares="10",
            max_jobs="100",
            max_wall_pj="60",
        )
        cursor = acct_conn.cursor()
        num_rows = cursor.execute("DELETE FROM association_table").rowcount

        self.assertEqual(num_rows, 1)

    # adding a user with the same primary key (user_name, account) should
    # return an IntegrityError
    def test_02_add_duplicate_primary_key(self):
        aclif.add_user(
            acct_conn,
            username="fluxuser",
            admin_level="1",
            bank="acct",
            shares="10",
            max_jobs="100",
            max_wall_pj="60",
        )
        aclif.add_user(
            acct_conn,
            username="fluxuser",
            admin_level="1",
            bank="acct",
            shares="10",
            max_jobs="100",
            max_wall_pj="60",
        )

        self.assertRaises(sqlite3.IntegrityError)

    # adding a user with the same username BUT a different account should
    # succeed
    def test_03_add_duplicate_user(self):
        aclif.add_user(
            acct_conn,
            username="dup_user",
            admin_level="1",
            bank="acct",
            shares="10",
            max_jobs="100",
            max_wall_pj="60",
        )
        aclif.add_user(
            acct_conn,
            username="dup_user",
            admin_level="1",
            bank="other_acct",
            shares="10",
            max_jobs="100",
            max_wall_pj="60",
        )
        cursor = acct_conn.cursor()
        cursor.execute("SELECT * from association_table where user_name='dup_user'")
        num_rows = cursor.execute(
            "DELETE FROM association_table where user_name='dup_user'"
        ).rowcount

        self.assertEqual(num_rows, 2)

    # edit a value for a user in the association table
    def test_04_edit_user_value(self):
        aclif.edit_user(acct_conn, "fluxuser", "max_jobs", "10000")
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT max_jobs FROM association_table where user_name='fluxuser'"
        )

        self.assertEqual(cursor.fetchone()[0], 10000)

    # trying to edit a field in a column that doesn't
    # exist should return an OperationalError
    def test_05_edit_bad_field(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.edit_user(acct_conn, "fluxuser", "foo", "bar")

        self.assertEqual(cm.exception.code, 1)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("FluxAccounting.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
