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
from unittest import mock

from fluxacct.accounting import job_usage_calculation as facade
from fluxacct.accounting.usage_calculators import (
    JobUsageCalculator,
    PeriodicUsageCalculator,
)


class TestUsageCalculators(unittest.TestCase):
    def test_base_calculator_is_abstract(self):
        with self.assertRaises(TypeError):
            JobUsageCalculator(mock.sentinel.conn)

    def test_periodic_calculator_satisfies_contract(self):
        self.assertTrue(issubclass(PeriodicUsageCalculator, JobUsageCalculator))
        calculator = PeriodicUsageCalculator(mock.sentinel.conn)
        self.assertEqual(calculator.conn, mock.sentinel.conn)

    @mock.patch.object(facade, "PeriodicUsageCalculator")
    def test_update_job_usage_delegates(self, calculator_cls):
        calculator_cls.return_value.update.return_value = mock.sentinel.result

        result = facade.update_job_usage(mock.sentinel.conn)

        calculator_cls.assert_called_once_with(mock.sentinel.conn)
        calculator_cls.return_value.update.assert_called_once_with()
        self.assertEqual(result, mock.sentinel.result)

    @mock.patch.object(facade, "PeriodicUsageCalculator")
    def test_connection_helper_wrappers_delegate(self, calculator_cls):
        calculator = calculator_cls.return_value

        facade.update_t_inactive(mock.sentinel.conn, 42, "user", "bank")
        facade.update_hist_usg_col(mock.sentinel.conn, 3.5, "user", "bank")
        facade.update_curr_usg_col(mock.sentinel.conn, 2.5, "user", "bank", 1000)
        facade.apply_decay_factor(mock.sentinel.conn, "user", "bank", 1000)
        facade.check_end_hl(mock.sentinel.conn, 3600)

        calculator.update_last_job_timestamp.assert_called_once_with(42, "user", "bank")
        calculator.update_association_usage.assert_called_once_with(3.5, "user", "bank")
        calculator.update_current_usage_bin.assert_called_once_with(
            2.5, "user", "bank", 1000
        )
        calculator.apply_decay_factor.assert_called_once_with("user", "bank", 1000)
        calculator.advance_half_life_period.assert_called_once_with(3600)
        self.assertEqual(
            calculator_cls.call_args_list,
            [mock.call(mock.sentinel.conn)] * 5,
        )

    @mock.patch.object(facade, "PeriodicUsageCalculator")
    def test_usage_factor_wrapper_delegates(self, calculator_cls):
        calculator = calculator_cls.return_value
        calculator.calculate_usage_factor.return_value = mock.sentinel.result
        user_jobs = []

        result = facade.calc_usage_factor(
            mock.sentinel.conn,
            3600,
            "user",
            "bank",
            1000,
            7200,
            user_jobs,
            1.0,
            0.5,
            0.25,
        )

        calculator.calculate_usage_factor.assert_called_once_with(
            3600,
            "user",
            "bank",
            1000,
            7200,
            user_jobs,
            1.0,
            0.5,
            0.25,
        )
        calculator_cls.assert_called_once_with(mock.sentinel.conn)
        self.assertEqual(result, mock.sentinel.result)

    @mock.patch.object(JobUsageCalculator, "calculate_hierarchical_bank_usage")
    @mock.patch.object(JobUsageCalculator, "calculate_bank_usage")
    @mock.patch.object(JobUsageCalculator, "get_usage_weights")
    def test_cursor_helper_wrappers_delegate(self, get_weights, calc_bank, calc_parent):
        get_weights.return_value = mock.sentinel.weights
        calc_bank.return_value = mock.sentinel.bank_usage
        calc_parent.return_value = mock.sentinel.parent_usage

        self.assertEqual(
            facade.get_usage_weights(mock.sentinel.cursor), mock.sentinel.weights
        )
        self.assertEqual(
            facade.calc_bank_usage(mock.sentinel.cursor, "bank"),
            mock.sentinel.bank_usage,
        )
        self.assertEqual(
            facade.calc_parent_bank_usage(
                mock.sentinel.conn, mock.sentinel.cursor, "bank"
            ),
            mock.sentinel.parent_usage,
        )

        get_weights.assert_called_once_with(mock.sentinel.cursor)
        calc_bank.assert_called_once_with(mock.sentinel.cursor, "bank")
        calc_parent.assert_called_once_with(mock.sentinel.cursor, "bank")


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
