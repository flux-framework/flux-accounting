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
import math
import unittest
from datetime import datetime

from fluxacct import util


class TestParseTimestamp(unittest.TestCase):
    def test_human_readable_formats(self):
        for value in (
            "01/01/2025",
            "2025-01-01 00:00:00",
            "Jan 1, 2025 12am",
        ):
            with self.subTest(value=value):
                timestamp = util.parse_timestamp(value)
                self.assertIsInstance(timestamp, (int, float))
                self.assertTrue(math.isfinite(timestamp))

    def test_numeric_epoch_values(self):
        self.assertEqual(util.parse_timestamp(42), 42)
        self.assertEqual(util.parse_timestamp("42"), 42)
        self.assertEqual(util.parse_timestamp(42.5), 42.5)
        self.assertEqual(util.parse_timestamp("42.5"), 42.5)

    def test_invalid_basic_format_date(self):
        with self.assertRaisesRegex(ValueError, "not a valid timestamp"):
            util.parse_timestamp("20251301")

    def test_valid_basic_format_date(self):
        expected = int(datetime(2025, 1, 1).timestamp())
        self.assertEqual(util.parse_timestamp("20250101"), expected)

    def test_invalid_values(self):
        invalid_values = [
            "",
            "not-a-timestamp",
            math.nan,
            "nan",
            math.inf,
            "inf",
            -math.inf,
            "-inf",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "not a valid timestamp"):
                    util.parse_timestamp(value)


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
