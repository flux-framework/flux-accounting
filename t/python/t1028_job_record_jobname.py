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
import json
import unittest

from fluxacct.jobs import records as j


def valid_resources():
    return json.dumps(
        {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": "0-3", "gpu": "0"}}],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["node0"],
            },
        }
    )


def make_jobspec(name=None, command=None):
    jobspec = {"attributes": {"system": {"bank": "A"}}}
    if name is not None:
        jobspec["attributes"]["system"]["job"] = {"name": name}
    if command is not None:
        jobspec["tasks"] = [{"command": command}]
    return json.dumps(jobspec)


class TestJobRecordJobName(unittest.TestCase):
    def test_01_explicit_name_preferred(self):
        jobspec = make_jobspec(name="explicit", command=["/bin/fallback"])
        self.assertEqual(j.extract_job_name(jobspec), "explicit")

    def test_02_command_basename_fallback(self):
        jobspec = make_jobspec(command=["/usr/bin/fallback"])
        self.assertEqual(j.extract_job_name(jobspec), "fallback")

    def test_03_trailing_slash_returns_full_path(self):
        jobspec = make_jobspec(command=["/usr/bin/"])
        self.assertEqual(j.extract_job_name(jobspec), "/usr/bin/")

    def test_04_name_with_whitespace(self):
        jobspec = make_jobspec(name="name with whitespace")
        self.assertEqual(j.extract_job_name(jobspec), "name with whitespace")

    def test_05_incomplete_jobspec_has_no_name(self):
        self.assertIsNone(j.extract_job_name(make_jobspec()))

    def test_06_converted_job_record_exposes_jobname(self):
        row = (
            50001,
            1,
            0,
            10,
            20,
            "0",
            valid_resources(),
            make_jobspec(name="converted"),
            "",
            "A",
            10,
            10,
        )

        job_records = j.convert_to_obj([row])
        self.assertEqual(len(job_records), 1)
        self.assertEqual(job_records[0].jobname, "converted")

    def test_07_malformed_jobspec_has_no_name(self):
        for jobspec in [
            "not json",
            "",
            "null",
            '{"attributes": null}',
            '{"attributes": {"system": {"job": null}}}',
        ]:
            with self.subTest(jobspec=jobspec):
                self.assertIsNone(j.extract_job_name(jobspec))

    def test_08_malformed_jobspec_does_not_drop_job(self):
        row = (
            50001,
            1,
            0,
            10,
            20,
            "0",
            valid_resources(),
            "not json",
            "",
            "A",
            10,
            10,
        )

        job_records = j.convert_to_obj([row])
        self.assertEqual(len(job_records), 1)
        self.assertIsNone(job_records[0].jobname)


def suite():
    suite = unittest.TestSuite()
    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
