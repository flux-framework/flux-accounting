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
import sys
from collections import defaultdict
from collections import namedtuple

from unittest import mock

from flux.constants import FLUX_USERID_UNKNOWN
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting import create_db as c
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b

# create a tuple-compatible ctruct like pwd.struct_passwd
struct_passwd = namedtuple(
    "struct_passwd",
    "pw_name pw_passwd pw_uid pw_gid pw_gecos pw_dir pw_shell",
)

# build fake passwd entries for the unit tests below
FAKE_ASSOCIATIONS = {
    50001: struct_passwd("50001", "x", 50001, 50001, "", "/home/50001", "/bin/bash"),
    50002: struct_passwd("50002", "x", 50002, 50002, "", "/home/50002", "/bin/bash"),
    50003: struct_passwd("50003", "x", 50003, 50003, "", "/home/50003", "/bin/bash"),
    50004: struct_passwd("50004", "x", 50004, 50004, "", "/home/50004", "/bin/bash"),
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


class TestAccountingCLI(unittest.TestCase):
    # create accounting database
    @classmethod
    def setUpClass(self):
        global conn
        global cur
        global user_jobs

        # create example job-archive database, output file
        c.create_db("FluxAccountingTest.db")
        try:
            conn = sqlite3.connect("file:FluxAccountingTest.db?mode=rw", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

        # simulate end of half life period in FluxAccounting database
        update_stmt = """
           UPDATE t_half_life_period_table SET end_half_life_period=?
           WHERE cluster='cluster'
           """
        conn.execute(update_stmt, ("10000000",))
        conn.commit()

        # add bank hierarchy
        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, bank="A", parent_bank="root", shares=1)
        b.add_bank(conn, bank="B", parent_bank="root", shares=1)

        # add associations
        u.add_user(conn, username="50001", uid=50001, bank="A")
        u.add_user(conn, username="50002", uid=50002, bank="B")

        jobid = 100
        interval = 0  # add to job timestamps to diversify job-archive records

        @mock.patch("time.time", mock.MagicMock(return_value=9000000))
        def populate_job_archive_db(conn, userid, bank, ranks, nodes, num_entries):
            nonlocal jobid
            nonlocal interval
            t_inactive_delta = 2000

            R_input = """{{
             "version": 1,
             "execution": {{
               "R_lite": [
                 {{
                   "rank": "{rank}",
                   "children": {{
                       "core": "0-3",
                       "gpu": "0"
                    }}
                 }}
               ],
               "starttime": 0,
               "expiration": 0,
               "nodelist": [
                 "{nodelist}"
               ]
             }}
           }}
           """.format(
                rank=ranks, nodelist=nodes
            )

            for i in range(num_entries):
                try:
                    conn.execute(
                        """
                       INSERT INTO jobs (
                           id,
                           userid,
                           t_submit,
                           t_run,
                           t_inactive,
                           ranks,
                           R,
                           jobspec,
                           bank
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """,
                        (
                            jobid,
                            userid,
                            (time.time() + interval) - 2000,
                            (time.time() + interval),
                            (time.time() + interval) + t_inactive_delta,
                            ranks,
                            R_input,
                            '{ "attributes": { "system": { "bank": "' + bank + '"} } }',
                            bank,
                        ),
                    )
                    # commit changes
                    conn.commit()
                # make sure entry is unique
                except sqlite3.IntegrityError as integrity_error:
                    print(integrity_error)

                jobid += 1
                interval += 10000
                t_inactive_delta += 100

        # populate the job-archive DB with fake job entries
        populate_job_archive_db(conn, 50001, "A", "0", "fluke[0]", 2)

        populate_job_archive_db(conn, 50002, "B", "0-1", "fluke[0-1]", 3)
        populate_job_archive_db(conn, 50002, "B", "0", "fluke[0]", 2)

        job_records = j.convert_to_obj(j.get_jobs(conn))
        # convert jobs to dictionary to be referenced in unit tests below
        user_jobs = defaultdict(list)
        for job in job_records:
            key = (job.userid, job.bank)
            user_jobs[key].append(job)

    # With the above job submissions, total usage will look like the following:
    # Bank  Username  RawUsage
    # ------------------------
    # root             20800.0
    #  A                4100.0
    #   A      50001    4100.0
    #  B               16700.0
    #   B      50002   16700.0
    @mock.patch("time.time", mock.MagicMock(return_value=(9000000)))
    def test_01_update_job_usage(self):
        jobs.update_job_usage(conn)
        # ensure usage is accurate across root bank and sub banks
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        bank_root_usage = cur.fetchone()[0]
        self.assertEqual(bank_root_usage, 20800.0)
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        bank_A_usage = cur.fetchone()[0]
        self.assertEqual(bank_A_usage, 4100.0)
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='B'")
        bank_B_usage = cur.fetchone()[0]
        self.assertEqual(bank_B_usage, 16700.0)

    # After deleting one of the banks, the rest of the hierarchy needs to be updated and
    # will look like:
    # Bank  Username  RawUsage
    # ------------------------
    # root             16700.0
    #  B               16700.0
    #   B      50002   16700.0
    @mock.patch("time.time", mock.MagicMock(return_value=(9000000)))
    def test_02_delete_bank_A(self):
        b.delete_bank(conn, "A", force=True)
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        bank_root_usage = cur.fetchone()[0]
        self.assertEqual(bank_root_usage, 16700.0)
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='B'")
        bank_B_usage = cur.fetchone()[0]
        self.assertEqual(bank_B_usage, 16700.0)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        os.remove("FluxAccountingTest.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
