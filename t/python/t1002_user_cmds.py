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
import io
import sys

from unittest import mock

from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("TestUserSubcommands.db")
        global acct_conn
        try:
            acct_conn = sqlite3.connect("file:TestUserSubcommands.db?mode=rw", uri=True)
            acct_conn.row_factory = sqlite3.Row
            cur = acct_conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

    # add a valid user to association_table
    def test_01_add_valid_user(self):
        b.add_bank(acct_conn, bank="acct", shares=10)
        u.add_user(
            acct_conn,
            username="fluxuser",
            uid="1234",
            bank="acct",
            shares="10",
            queues="",
        )
        cursor = acct_conn.cursor()
        num_rows_assoc_table = cursor.execute("DELETE FROM association_table").rowcount
        num_rows_job_usage_factor_table = cursor.execute(
            "DELETE FROM job_usage_factor_table"
        ).rowcount

        self.assertEqual(num_rows_assoc_table, num_rows_job_usage_factor_table)

    # adding a user with the same primary key (username, bank) should
    # return an IntegrityError
    def test_02_add_duplicate_primary_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            u.add_user(
                acct_conn,
                username="fluxuser",
                uid="1234",
                bank="acct",
                shares="10",
                queues="",
            )
            u.add_user(
                acct_conn,
                username="fluxuser",
                uid="1234",
                bank="acct",
                shares="10",
                queues="",
            )

    # add a user with the same username but a different bank
    def test_03_add_duplicate_user(self):
        b.add_bank(acct_conn, bank="other_acct", parent_bank="acct", shares=10)
        u.add_user(
            acct_conn,
            username="dup_user",
            uid="5678",
            bank="acct",
            shares="10",
            queues="",
        )
        u.add_user(
            acct_conn,
            username="dup_user",
            uid="5678",
            bank="other_acct",
            shares="10",
            queues="",
        )
        cursor = acct_conn.cursor()
        cursor.execute("SELECT * from association_table where username='dup_user'")
        num_rows = cursor.execute(
            "DELETE FROM association_table where username='dup_user'"
        ).rowcount

        self.assertEqual(num_rows, 2)

    # edit a value for a user in the association table
    def test_04_edit_user_value(self):
        u.edit_user(
            acct_conn,
            username="fluxuser",
            bank="acct",
            shares=10000,
        )
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM association_table where username='fluxuser'")

        self.assertEqual(cursor.fetchone()[0], 10000)

    # reset a value for a user in the association table by
    # passing -1
    def test_05_edit_reset_user_value(self):
        u.edit_user(
            acct_conn,
            username="fluxuser",
            bank="acct",
            shares="-1",
        )
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM association_table where username='fluxuser'")

        self.assertEqual(cursor.fetchone()[0], 1)

    # disable a user from the association table
    def test_06_delete_user(self):
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT * FROM association_table WHERE username='fluxuser' AND bank='acct'"
        )
        num_rows_before_delete = cursor.fetchall()

        self.assertEqual(len(num_rows_before_delete), 1)

        u.delete_user(acct_conn, username="fluxuser", bank="acct")

        cursor.execute(
            "SELECT active FROM association_table WHERE username='fluxuser' AND bank='acct'"
        )
        rows = cursor.fetchall()

        self.assertEqual(rows[0][0], 0)

    # check for a new user's default bank
    def test_07_check_default_bank_new_user(self):
        b.add_bank(acct_conn, bank="test_bank", parent_bank="acct", shares=10)
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
        b.add_bank(acct_conn, bank="other_test_bank", parent_bank="acct", shares=10)
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
        u.edit_user(
            acct_conn,
            username="test_user1",
            default_bank="other_test_bank",
        )
        cursor = acct_conn.cursor()
        cursor.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user1'"
        )

        self.assertEqual(cursor.fetchone()[0], "other_test_bank")

    def test_10_view_nonexistent_user(self):
        with self.assertRaises(ValueError):
            u.view_user(acct_conn, "foo")

    # disable a user who belongs to multiple banks; make sure that the default_bank
    # is updated to the next earliest associated bank
    def test_11_disable_user_default_bank_row(self):
        b.add_bank(acct_conn, bank="A", parent_bank="acct", shares=1)
        b.add_bank(acct_conn, bank="B", parent_bank="acct", shares=1)
        u.add_user(acct_conn, username="test_user2", bank="A")
        u.add_user(acct_conn, username="test_user2", bank="B")
        cur = acct_conn.cursor()
        cur.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user2'"
        )

        self.assertEqual(cur.fetchone()[0], "A")

        u.delete_user(acct_conn, username="test_user2", bank="A")
        cur.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user2'"
        )

        self.assertEqual(cur.fetchone()[0], "B")

    # disable a user who only belongs to one bank; make sure that the default_bank
    # stays the same after disabling
    def test_12_disable_user_default_bank_row_2(self):
        u.add_user(acct_conn, username="test_user3", bank="A")
        cur = acct_conn.cursor()
        cur.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user3'"
        )

        self.assertEqual(cur.fetchone()[0], "A")

        u.delete_user(acct_conn, username="test_user3", bank="A")

        cur.execute(
            "SELECT default_bank FROM association_table WHERE username='test_user3'"
        )

        self.assertEqual(cur.fetchone()[0], "A")

    # adding a user to a nonexistent bank should raise a ValueError
    def test_13_add_user_to_nonexistent_bank(self):
        with self.assertRaises(ValueError):
            u.add_user(acct_conn, username="test_user4", bank="foo")

    # edit a user's userid
    def test_14_edit_user_userid(self):
        cur = acct_conn.cursor()
        u.add_user(acct_conn, username="test_user5", bank="A")

        cur.execute("SELECT userid FROM association_table WHERE username='test_user5'")
        self.assertEqual(cur.fetchone()[0], 65534)

        u.edit_user(acct_conn, username="test_user5", userid="12345")
        cur.execute("SELECT userid FROM association_table WHERE username='test_user5'")
        self.assertEqual(cur.fetchone()[0], 12345)

    # adding a user with a nonexistent queue should raise a ValueError
    def test_15_add_user_with_nonexistent_queue(self):
        with self.assertRaises(ValueError):
            u.add_user(acct_conn, username="test_user4", bank="A", queues="foo")

    # adding a user with a nonexistent project should raise a ValueError
    def test_15_add_user_with_nonexistent_project(self):
        with self.assertRaises(ValueError):
            u.add_user(acct_conn, username="test_user4", bank="A", projects="foo")

    # edit a user's fair-share value
    def test_16_edit_user_fairshare(self):
        cur = acct_conn.cursor()
        cur.execute(
            "SELECT fairshare FROM association_table WHERE username='test_user5'"
        )
        fairshare = cur.fetchall()
        self.assertEqual(fairshare[0][0], 0.5)

        u.edit_user(acct_conn, username="test_user5", fairshare=0.95)
        cur.execute(
            "SELECT fairshare FROM association_table WHERE username='test_user5'"
        )
        fairshare = cur.fetchall()
        self.assertEqual(fairshare[0][0], 0.95)

    # actually remove a user from the association_table
    def test_17_delete_user_force(self):
        cur = acct_conn.cursor()
        select_stmt = "SELECT * FROM association_table WHERE username='test_user5'"
        cur.execute(select_stmt)
        result = cur.fetchall()
        self.assertEqual(len(result), 1)

        # pass force=True to actually remove the user row from the table
        u.delete_user(acct_conn, username="test_user5", bank="A", force=True)
        cur.execute(select_stmt)
        result = cur.fetchall()
        self.assertEqual(len(result), 0)

    # actually remove a user from the association_table where their default
    # bank needs to be updated
    def test_18_delete_user_force_update_bank(self):
        cur = acct_conn.cursor()
        select_stmt = (
            "SELECT default_bank FROM association_table WHERE username='test_user6'"
        )
        # add two associations
        u.add_user(acct_conn, username="test_user6", bank="A")
        u.add_user(acct_conn, username="test_user6", bank="B")
        cur.execute(select_stmt)
        default_bank = cur.fetchall()
        self.assertEqual(default_bank[0][0], "A")

        # delete one of the rows with force=True
        u.delete_user(acct_conn, username="test_user6", bank="A", force=True)
        cur.execute(select_stmt)
        default_bank = cur.fetchall()
        self.assertEqual(default_bank[0][0], "B")

    # pass a bad kwarg to edit_all_users(); ensure a ValueError is raised
    def test_19_edit_all_users_bad_kwarg(self):
        with self.assertRaises(ValueError) as err:
            u.edit_all_users(acct_conn, foo="bar")

        self.assertIn("unrecognized argument(s) passed: ['foo']", str(err.exception))

    # set job_usage to True to get breakdown of job usage
    def test_20_view_user_job_usage_no_usage(self):
        result = u.view_user(acct_conn, user="test_user5", job_usage=True)

        self.assertIn("username", result)
        self.assertIn("bank", result)
        self.assertIn("last_job_timestamp", result)
        self.assertIn("usage_factor_period_0", result)
        self.assertIn("usage_factor_period_1", result)
        self.assertIn("usage_factor_period_2", result)
        self.assertIn("usage_factor_period_3", result)
        self.assertIn("test_user5", result)
        self.assertIn("A", result)
        self.assertIn("0.0", result)

    # edit the job usage columns and make suer they are populated in result
    def test_21_view_user_job_usage_usage(self):
        cur = acct_conn.cursor()
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=1.23 "
            "WHERE username='test_user5'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_1=4.56 "
            "WHERE username='test_user5'"
        )
        acct_conn.commit()
        result = u.view_user(acct_conn, user="test_user5", job_usage=True)
        self.assertIn("1.23", result)
        self.assertIn("4.56", result)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestUserSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
