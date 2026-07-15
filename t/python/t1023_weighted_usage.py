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
import json
from collections import defaultdict
from collections import namedtuple

from unittest import mock

from flux.constants import FLUX_USERID_UNKNOWN
from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting import db_info_subcommands as d


# create a tuple-compatible struct like pwd.struct_passwd
struct_passwd = namedtuple(
    "struct_passwd",
    "pw_name pw_passwd pw_uid pw_gid pw_gecos pw_dir pw_shell",
)

# build fake passwd entries for the unit tests
FAKE_ASSOCIATIONS = {
    50001: struct_passwd("user1", "x", 50001, 50001, "", "/home/user1", "/bin/bash"),
}


# helper lookup functions to overwrite those in accounting.util
def fake_get_uid(uid):
    try:
        return FAKE_ASSOCIATIONS[int(uid)].pw_uid
    except KeyError:
        return FLUX_USERID_UNKNOWN


def fake_get_username(name):
    for entry in FAKE_ASSOCIATIONS.values():
        if entry.pw_name == name:
            return entry
    return str(name)


class TestWeightedUsage(unittest.TestCase):
    @staticmethod
    def insert_job(
        job_id, userid, bank, t_submit, t_run, t_inactive, ncores=4, ngpus=1
    ):
        """Insert a job with specified ncores and ngpus."""
        # Handle edge cases: ncores must be at least 1 (jobs need cores to run)
        if ncores < 1:
            ncores = 1
        # ngpus can be 0 (jobs without GPUs are valid)
        if ngpus < 0:
            ngpus = 0

        if ncores == 1:
            core_str = "0"
        else:
            core_str = f"0-{ncores-1}"

        # Build children dict
        children = {"core": core_str}
        if ngpus == 1:
            children["gpu"] = "0"
        elif ngpus > 1:
            children["gpu"] = f"0-{ngpus-1}"

        R = json.dumps(
            {
                "version": 1,
                "execution": {
                    "R_lite": [
                        {
                            "rank": "0",
                            "children": children,
                        }
                    ],
                    "starttime": 0,
                    "expiration": 0,
                    "nodelist": ["fluke[0]"],
                },
            }
        )
        jobspec = json.dumps({"attributes": {"system": {"bank": bank}}})
        conn.execute(
            "INSERT INTO jobs "
            "(id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, userid, t_submit, t_run, t_inactive, "0", R, jobspec, bank),
        )
        conn.commit()
        print(f"inserted job successfully")

    @classmethod
    @mock.patch("time.time", mock.MagicMock(return_value=0))
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(
            self.dbname,
            priority_decay_half_life="15m",
            priority_usage_reset_period="1h",
        )
        global conn
        global cursor

        conn = sqlite3.connect(self.dbname, timeout=60)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # simulate end of half life period
        update_stmt = """
            UPDATE t_half_life_period_table SET end_half_life_period=?
            WHERE cluster='cluster'
            """
        conn.execute(update_stmt, ("0",))
        conn.commit()

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)

        conn.commit()

    @mock.patch("time.time", mock.MagicMock(return_value=600))
    def test_01_default_weights_backward_compatible(self):
        # insert a job with the following properties:
        # 1 node, 4 cores, 1 GPU, 100 seconds elapsed
        self.insert_job(1, 50001, "A", 1, 499, 599, ncores=4, ngpus=1)
        jobs.update_job_usage(conn)

        # with default weights, usage for this job becomes:
        # ((1 * 1.0) + (4 * 0.0) + (1 * 0.0)) * 100 = 100.0
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("100.0", total_usage)

    @mock.patch("time.time", mock.MagicMock(return_value=1200))
    def test_02_core_weight_increases_usage(self):
        # clear existing jobs and usage
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        jobs.clear_usage(conn, ["A"], ignore_older_than="0")

        # Set core_weight = 1.0
        d.edit_config(conn, ["core_weight=1.0"])
        cursor.execute("SELECT value FROM config_table WHERE key='core_weight'")
        self.assertEqual(float(cursor.fetchone()[0]), 1.0)

        self.insert_job(2, 50001, "A", 1, 1099, 1199, ncores=4, ngpus=0)
        jobs.update_job_usage(conn)

        # with the core weight now set to 1.0, usage becomes:
        # ((1 * 1.0) + (4 * 1.0) + (0 * 0.0)) * 100 = 500.0
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("500.0", total_usage)

    @mock.patch("time.time", mock.MagicMock(return_value=2400))
    def test_03_gpu_weight_increases_usage(self):
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        jobs.clear_usage(conn, ["A"], ignore_older_than="0")
        d.edit_config(conn, ["node_weight=1.0", "core_weight=0.0", "gpu_weight=10.0"])

        self.insert_job(3, 50001, "A", 1, 2299, 2399, ncores=4, ngpus=2)
        jobs.update_job_usage(conn)

        # with the GPU weight now configured, usage becomes:
        # ((1 * 1.0) + (4 * 0.0) + (2 * 10.0)) * 100 = 2100.0
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("2100.0", total_usage)

    @mock.patch("time.time", mock.MagicMock(return_value=3600))
    def test_04_mixed_weights(self):
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        jobs.clear_usage(conn, ["A"], ignore_older_than="0")
        d.edit_config(conn, ["node_weight=1.0", "core_weight=0.5", "gpu_weight=5.0"])

        self.insert_job(4, 50001, "A", 1, 3499, 3599, ncores=8, ngpus=2)
        jobs.update_job_usage(conn)

        # with weights (1.0, 0.5, 5.0), usage becomes:
        # ((1 * 1.0) + (8 * 0.5) + (2 * 5.0)) * 100 = (2 + 4 + 10) * 100 = 1500.0
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("1500.0", total_usage)

    # test get_usage_weights helper function
    def test_05_get_usage_weights_helper(self):
        d.edit_config(conn, ["node_weight=2.0", "core_weight=0.1", "gpu_weight=3.5"])

        cur = conn.cursor()
        node_weight, core_weight, gpu_weight = jobs.get_usage_weights(cur)
        self.assertEqual(node_weight, 2.0)
        self.assertEqual(core_weight, 0.1)
        self.assertEqual(gpu_weight, 3.5)

    # ensure resource weights cannot be removed from config_table
    def test_06_no_delete_resource_weights(self):
        with self.assertRaisesRegex(
            ValueError, "key-value pair is not allowed to be removed from config_table"
        ):
            d.delete_config(conn, "node_weight")
        with self.assertRaisesRegex(
            ValueError, "key-value pair is not allowed to be removed from config_table"
        ):
            d.delete_config(conn, "core_weight")
        with self.assertRaisesRegex(
            ValueError, "key-value pair is not allowed to be removed from config_table"
        ):
            d.delete_config(conn, "gpu_weight")

    # manually delete a resource weight from config_table; ensure usage can still fall
    # back to a default value
    @mock.patch("time.time", mock.MagicMock(return_value=600))
    def test_07_resource_weight_fall_back_to_default(self):
        cursor.execute("DELETE FROM config_table WHERE key='node_weight'")
        # clear existing jobs and usage
        cursor.execute("DELETE FROM jobs")
        conn.commit()
        jobs.clear_usage(conn, ["A"], ignore_older_than="0")

        # reset core, GPU weights
        d.edit_config(conn, ["core_weight=0.0", "gpu_weight=0.0"])

        self.insert_job(5, 50001, "A", 1, 499, 599, ncores=4, ngpus=0)
        jobs.update_job_usage(conn)

        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("100.0", total_usage)

    def test_08_resource_weight_not_a_number(self):
        # ensure that configuring weights to a value other than a float fails
        with self.assertRaisesRegex(
            ValueError, "could not convert string to float: 'foo'"
        ):
            d.edit_config(conn, ["node_weight=foo"])
        with self.assertRaisesRegex(
            ValueError, "could not convert string to float: 'foo'"
        ):
            d.edit_config(conn, ["core_weight=foo"])
        with self.assertRaisesRegex(
            ValueError, "could not convert string to float: 'foo'"
        ):
            d.edit_config(conn, ["gpu_weight=foo"])

    @classmethod
    def tearDownClass(self):
        os.remove(self.dbname)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
