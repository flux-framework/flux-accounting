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
import re

from fluxacct.accounting import create_db as c
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import visuals as vis


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test flux-accounting database
        c.create_db("FluxAccountingVisuals.db")
        global conn
        global cur

        conn = sqlite3.connect("FluxAccountingVisuals.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, parent_bank="root", bank="A", shares=1)
        b.add_bank(conn, parent_bank="root", bank="B", shares=1)
        b.add_bank(conn, parent_bank="root", bank="C", shares=1)

        u.add_user(conn, username="user1", bank="A")
        u.add_user(conn, username="user2", bank="A")
        u.add_user(conn, username="user3", bank="B")
        u.add_user(conn, username="user4", bank="B")
        u.add_user(conn, username="user5", bank="C")

        cur.execute("UPDATE association_table SET job_usage=5  WHERE username='user1'")
        cur.execute("UPDATE association_table SET job_usage=14 WHERE username='user2'")
        cur.execute("UPDATE association_table SET job_usage=7  WHERE username='user3'")
        cur.execute("UPDATE association_table SET job_usage=45 WHERE username='user4'")
        cur.execute("UPDATE association_table SET job_usage=23 WHERE username='user5'")

        cur.execute("UPDATE bank_table SET job_usage=19 WHERE bank='A'")
        cur.execute("UPDATE bank_table SET job_usage=52 WHERE bank='B'")
        cur.execute("UPDATE bank_table SET job_usage=23 WHERE bank='C'")

        conn.commit()

    @staticmethod
    def extract_values(output):
        """
        Given the multi-line bar graph output, grab the float at the
        end of each line and return them as a list of floats.
        """
        vals = []
        for line in output.splitlines():
            m = re.search(r"([0-9]+\.[0-9]+)\s*$", line)
            vals.append(float(m.group(1)))
        return vals

    def test_01_show_usage_associations_default(self):
        test = vis.show_usage(conn, table="associations")
        vals = self.extract_values(test)
        # ensure the order of the y-axis is in reverse order (i.e. largest job usage
        # value at the top of the graph)
        self.assertTrue(vals, sorted(vals, reverse=True))

        y_axis = test.splitlines()
        # check order of y-axis
        self.assertEqual(y_axis[0].split("|")[0].strip(), "user4 / B")
        self.assertEqual(y_axis[1].split("|")[0].strip(), "user5 / C")
        self.assertEqual(y_axis[2].split("|")[0].strip(), "user2 / A")
        self.assertEqual(y_axis[3].split("|")[0].strip(), "user3 / B")
        self.assertEqual(y_axis[4].split("|")[0].strip(), "user1 / A")

    def test_02_show_usage_banks_default(self):
        test = vis.show_usage(conn, table="banks")
        vals = self.extract_values(test)
        # ensure the order of the y-axis is in reverse order (i.e. largest job usage
        # value at the top of the graph)
        self.assertTrue(vals, sorted(vals, reverse=True))

        y_axis = test.splitlines()
        # check order of y-axis
        self.assertEqual(y_axis[0].split("|")[0].strip(), "B")
        self.assertEqual(y_axis[1].split("|")[0].strip(), "C")
        self.assertEqual(y_axis[2].split("|")[0].strip(), "A")

    def test_03_show_usage_associations_custom(self):
        test = vis.show_usage(conn, table="associations", limit=1)

        y_axis = test.splitlines()
        # make sure only one result is returned
        self.assertEqual(len(y_axis), 1)

        self.assertEqual(y_axis[0].split("|")[0].strip(), "user4 / B")

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("FluxAccountingVisuals.db")


def suite():
    unittest.TestSuite()


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
