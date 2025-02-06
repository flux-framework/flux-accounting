#!/usr/bin/env python3

###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
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
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import project_subcommands as p


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("TestProjectSubcommands.db")
        global acct_conn
        global cur

        acct_conn = sqlite3.connect("TestProjectSubcommands.db")
        acct_conn.row_factory = sqlite3.Row
        cur = acct_conn.cursor()

    # add a valid project to project_table
    def test_01_add_valid_projects(self):
        p.add_project(acct_conn, project="project_1")
        cur.execute("SELECT * FROM project_table WHERE project='project_1'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_02_add_dup_project(self):
        with self.assertRaises(sqlite3.IntegrityError):
            p.add_project(acct_conn, project="project_1")

    # remove a project currently in the project_table
    def test_03_delete_project(self):
        p.delete_project(acct_conn, project="project_1")
        cur.execute("SELECT * FROM project_table WHERE project='project_1'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 0)

    # add a user to the accounting DB without specifying a default project
    def test_04_default_project_unspecified(self):
        b.add_bank(acct_conn, bank="A", shares=1)
        u.add_user(acct_conn, username="user5001", uid=5001, bank="A")
        cur.execute(
            "SELECT default_project FROM association_table WHERE username='user5001' AND bank='A'"
        )
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], "*")

    # add a user to the accounting DB by specifying a default project
    def test_05_default_project_specified(self):
        p.add_project(acct_conn, project="project_1")
        u.add_user(
            acct_conn, username="user5002", uid=5002, bank="A", projects="project_1"
        )
        cur.execute(
            "SELECT default_project FROM association_table WHERE username='user5002' AND bank='A'"
        )
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], "project_1")

        # make sure "*" is also added to the user's project list
        cur.execute(
            "SELECT projects FROM association_table WHERE username='user5002' AND bank='A'"
        )
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], "project_1,*")

    # edit a user's default project
    def test_06_edit_default_project(self):
        u.edit_user(acct_conn, username="user5002", bank="A", default_project="*")
        cur.execute(
            "SELECT default_project FROM association_table WHERE username='user5002' AND bank='A'"
        )
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], "*")

        # make sure projects list gets edited correctly
        u.edit_user(acct_conn, username="user5002", bank="A", projects="project_1")
        cur.execute(
            "SELECT projects FROM association_table WHERE username='user5002' AND bank='A'"
        )
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], "project_1,*")

    # editing a user's project list with a bad project name should raise a ValueError
    def test_07_edit_projects_list_bad_name(self):
        with self.assertRaises(ValueError):
            u.edit_user(acct_conn, username="user5002", bank="A", projects="foo")

    # trying to view a project that does not exist should raise a ValueError
    def test_08_view_project_nonexistent(self):
        with self.assertRaises(ValueError):
            p.view_project(acct_conn, "foo")

    # reset the lists of projects for an association
    def test_09_reset_projects_for_association(self):
        u.edit_user(acct_conn, username="user5002", projects=-1)
        cur.execute(
            "SELECT projects, default_project FROM association_table WHERE username='user5002' AND bank='A'"
        )
        rows = cur.fetchall()

        print(rows)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestProjectSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
