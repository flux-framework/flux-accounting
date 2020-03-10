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
import fairshare as f
import sys
import os


class TestFairshare(unittest.TestCase):

    # make sure user id can be read correctly
    def test_check_user_id_valid(self):
        expected = "user id specified: 10514"
        test = f.check_user_id(10514)
        self.assertEqual(test, expected)

    # make sure function returns -1 if string is passed
    def test_check_user_id_bad_val_str(self):
        expected = -1
        test = f.check_user_id("bad val")
        self.assertEqual(test, expected)

    # make sure function returns -1 if a float is passed
    def test_check_user_id_bad_val_float(self):
        expected = -1
        test = f.check_user_id(3.14159)
        self.assertEqual(test, expected)

    # fetch valid user's information from database
    def test_fetch_valid_user_info(self):
        expected = {"user_id": "12345", "acct": "lc", "shares": "1"}
        test = f.fetch_usr_data(12345)
        self.assertDictEqual(test, expected)

    # make sure invalid user id fails successfully
    def test_fetch_bad_user_id(self):
        expected = "user not found in database"
        test = f.fetch_usr_data(0)
        self.assertEqual(test, expected)


if __name__ == "__main__":
    unittest.main()
