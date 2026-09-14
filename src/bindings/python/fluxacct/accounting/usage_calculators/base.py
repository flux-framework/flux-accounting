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
from abc import ABC, abstractmethod


class JobUsageCalculator(ABC):
    """
    Base class for job-usage calculation strategies.

    Calculators operate on the SQLite connection supplied at construction and
    provide common operations for getting resource weights, association usage, and
    bank hierarchy aggregation.

    Subclasses implement update() to perform their strategy-specific calculation
    and database updates.
    """

    def __init__(self, conn):
        self.conn = conn

    @abstractmethod
    def update(self) -> int:
        """Update job usage in the accounting database."""

    def update_association_usage(self, usage, user, bank):
        """Update the historical job usage for an association."""
        u_usg = """
            UPDATE association_table SET job_usage=? WHERE username=? AND bank=?
            """
        self.conn.execute(u_usg, (usage, user, bank))

    @staticmethod
    def get_usage_weights(cur):
        """
        Fetch resource weights from config_table to be used when calculating the usage
        for a job.
        """
        cur.execute("""
            SELECT key, value FROM config_table
            WHERE key IN ('node_weight', 'core_weight', 'gpu_weight')
            """)
        weights = {row[0]: float(row[1]) for row in cur.fetchall()}
        return (
            weights.get("node_weight", 1.0),
            weights.get("core_weight", 0.0),
            weights.get("gpu_weight", 0.0),
        )

    @staticmethod
    def calculate_weighted_usage(job, node_weight, core_weight, gpu_weight):
        """Return a job's raw weighted resource usage."""
        return (
            (job.nnodes * node_weight)
            + (job.ncores * core_weight)
            + (job.ngpus * gpu_weight)
        ) * job.elapsed

    @staticmethod
    def calculate_bank_usage(cur, bank):
        """Calculate and store association usage for a bank."""
        s_associations = "SELECT job_usage FROM association_table WHERE bank=?"
        cur.execute(s_associations, (bank,))
        job_usage_list = cur.fetchall()

        total_usage = 0.0
        if job_usage_list:
            for job_usage in job_usage_list:
                total_usage += job_usage[0]

        u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
        cur.execute(u_job_usage, (total_usage, bank))

        return total_usage

    @staticmethod
    def calculate_hierarchical_bank_usage(cur, bank):
        """Recursively calculate and store usage for a bank hierarchy."""
        cur.execute("SELECT bank FROM bank_table WHERE parent_bank=?", (bank,))
        sub_banks = cur.fetchall()

        total_usage = 0.0
        if len(sub_banks) == 0:
            total_usage = JobUsageCalculator.calculate_bank_usage(cur, bank)
        else:
            for sub_bank in sub_banks:
                sub_usage = JobUsageCalculator.calculate_hierarchical_bank_usage(
                    cur, sub_bank[0]
                )
                total_usage += sub_usage

        u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
        cur.execute(u_job_usage, (total_usage, bank))

        return total_usage
