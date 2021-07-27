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

from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("TestAcctingSubcommands.db")
        global acct_conn
        global jobs_conn
        acct_conn = sqlite3.connect("TestAcctingSubcommands.db")

    # add a valid user to association_table
    def test_01_add_valid_user(self):
        u.add_user(
            acct_conn,
            username="fluxuser",
            uid="1234",
            admin_level="1",
            bank="acct",
            shares="10",
        )
        cursor = acct_conn.cursor()
        num_rows_assoc_table = cursor.execute("DELETE FROM association_table").rowcount
        num_rows_job_usage_factor_table = cursor.execute(
            "DELETE FROM job_usage_factor_table"
        ).rowcount

        self.assertEqual(num_rows_assoc_table, num_rows_job_usage_factor_table)

    # adding a user with the same primary key (username, account) should
    # return an IntegrityError
    def test_02_add_duplicate_primary_key(self):
        u.add_user(
            acct_conn,
            username="fluxuser",
            uid="1234",
            admin_level="1",
            bank="acct",
            shares="10",
        )
        u.add_user(
            acct_conn,
            username="fluxuser",
            uid="1234",
            admin_level="1",
            bank="acct",
            shares="10",
        )

        self.assertRaises(sqlite3.IntegrityError)

    # adding a user with the same username BUT a different account should
    # succeed
    def test_03_add_duplicate_user(self):
        u.add_user(
            acct_conn,
            username="dup_user",
            uid="5678",
            admin_level="1",
            bank="acct",
            shares="10",
        )
        u.add_user(
            acct_conn,
            username="dup_user",
            uid="5678",
            admin_level="1",
            bank="other_acct",
            shares="10",
        )
        cursor = acct_conn.cursor()
        cursor.execute("SELECT * from association_table where username='dup_user'")
        num_rows = cursor.execute(
            "DELETE FROM association_table where username='dup_user'"
        ).rowcount

        self.assertEqual(num_rows, 2)

    # edit a value for a user in the association table
    def test_04_edit_user_value(self):
        u.edit_user(acct_conn, "fluxuser", "shares", "10000")
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM association_table where username='fluxuser'")

        self.assertEqual(cursor.fetchone()[0], 10000)

    # trying to edit a field in a column that doesn't
    # exist should return a ValueError
    def test_05_edit_bad_field(self):
        with self.assertRaises(ValueError):
            u.edit_user(acct_conn, "fluxuser", "foo", "bar")

    # delete a user from the association table
    def test_06_delete_user(self):
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT * FROM association_table WHERE username='fluxuser' AND bank='acct'"
        )
        num_rows_before_delete = cursor.fetchall()

        self.assertEqual(len(num_rows_before_delete), 1)

        u.delete_user(acct_conn, username="fluxuser", bank="acct")

        cursor.execute(
            "SELECT * FROM association_table WHERE username='fluxuser' AND bank='acct'"
        )
        num_rows_after_delete = cursor.fetchall()

        self.assertEqual(len(num_rows_after_delete), 0)

    # check for a new user's default bank
    def test_07_check_default_bank_new_user(self):
        u.add_user(
            acct_conn,
            username="test_user1",
            uid="5000",
            bank="test_bank",
        )
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user1'"
        )

        self.assertEqual(cursor.fetchone()[0], "test_bank")

    # check for an existing user's default bank
    def test_08_check_default_bank_existing_user(self):
        u.add_user(
            acct_conn,
            username="test_user1",
            uid="5000",
            bank="other_test_bank",
        )
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user1'"
        )

        self.assertEqual(cursor.fetchone()[0], "test_bank")

    # check that we can successfully edit the default bank for a user
    def test_09_edit_default_bank(self):
        u.edit_user(acct_conn, "test_user1", "default_bank", "other_test_bank")
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user1'"
        )

        self.assertEqual(cursor.fetchone()[0], "other_test_bank")

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestAcctingSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
