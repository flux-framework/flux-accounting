
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
import sys
import os


class TestExample(unittest.TestCase):

    # make sure unit tests can be called from top-level dir
    def test_00_confirm_unittest_works(self):
        expected = 1
        test = 1
        self.assertEqual(test, expected)

# vi: ts=4 sw=4 expandtab
