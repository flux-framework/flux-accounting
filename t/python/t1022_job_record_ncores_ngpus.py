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

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import jobs_table_subcommands as j


class TestJobRecordResourceExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global conn
        global cursor

        conn = sqlite3.connect(self.dbname, timeout=60)
        cursor = conn.cursor()

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)

    def insert_job_with_R(self, job_id, userid, bank, R_dict):
        """Helper to insert a job with a specific R field."""
        R = json.dumps(R_dict)
        jobspec = json.dumps({"attributes": {"system": {"bank": bank}}})
        conn.execute(
            "INSERT INTO jobs "
            "(id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, userid, 0, 0, 100, "0", R, jobspec, bank),
        )
        conn.commit()

    # test basic extraction of ncores and ngpus from a valid R field
    def test_01_basic_extraction(self):
        R = {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": "0-3", "gpu": "0"}}],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["node0"],
            },
        }
        self.insert_job_with_R(1, 50001, "A", R)

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=1))
        self.assertEqual(len(job_records), 1)
        job = job_records[0]
        self.assertEqual(job.ncores, 4)
        self.assertEqual(job.ngpus, 1)
        self.assertEqual(job.nnodes, 1)

    # test extraction with multiple GPUs
    def test_02_multiple_gpus(self):
        R = {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": "0-7", "gpu": "0-3"}}],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["node0"],
            },
        }
        self.insert_job_with_R(2, 50001, "A", R)

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=2))
        self.assertEqual(len(job_records), 1)
        job = job_records[0]
        self.assertEqual(job.ncores, 8)
        self.assertEqual(job.ngpus, 4)

    # test extraction when job has cores but no GPUs
    def test_03_no_gpus(self):
        R = {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": "0-15"}}],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["node0"],
            },
        }
        self.insert_job_with_R(3, 50001, "A", R)

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=3))
        self.assertEqual(len(job_records), 1)
        job = job_records[0]
        self.assertEqual(job.ncores, 16)
        self.assertEqual(job.ngpus, 0)

    # test extraction for a multi-node job
    def test_04_multi_node(self):
        R = {
            "version": 1,
            "execution": {
                "R_lite": [
                    {"rank": "0", "children": {"core": "0-3", "gpu": "0-1"}},
                    {"rank": "1", "children": {"core": "0-3", "gpu": "0-1"}},
                ],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["node0", "node1"],
            },
        }
        self.insert_job_with_R(4, 50001, "A", R)

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=4))
        self.assertEqual(len(job_records), 1)
        job = job_records[0]
        self.assertEqual(job.nnodes, 2)
        self.assertEqual(job.ncores, 8)  # 4 cores per node * 2 nodes
        self.assertEqual(job.ngpus, 4)  # 2 gpus per node * 2 nodes

    # test that jobs with malformed R field are skipped gracefully
    def test_05_malformed_R_skipped(self):
        malformed_R = "not valid json at all"
        jobspec = json.dumps({"attributes": {"system": {"bank": "A"}}})
        conn.execute(
            "INSERT INTO jobs "
            "(id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (5, 50001, 0, 0, 100, "0", malformed_R, jobspec, "A"),
        )
        conn.commit()

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=5))
        self.assertEqual(len(job_records), 0)

    # test that R with missing version field is skipped
    def test_06_missing_version_skipped(self):
        invalid_R = json.dumps({"execution": {"nodelist": ["node0"]}})
        jobspec = json.dumps({"attributes": {"system": {"bank": "A"}}})
        conn.execute(
            "INSERT INTO jobs "
            "(id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (6, 50001, 0, 0, 100, "0", invalid_R, jobspec, "A"),
        )
        conn.commit()

        job_records = j.convert_to_obj(j.get_jobs(conn, jobid=6))
        self.assertEqual(len(job_records), 0)

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
