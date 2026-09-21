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
from collections import defaultdict


class JobUsageCalculator(ABC):
    """Base class for job-usage calculation strategies."""

    def __init__(self, conn):
        self.conn = conn

    @abstractmethod
    def update(self):
        """Update job usage according to the strategy."""

    def update_usage_col(self, usg_h, user, bank):
        """Update the job_usage column for the association."""
        u_usg = """
            UPDATE association_table SET job_usage=? WHERE username=? AND bank=?
            """
        self.conn.execute(
            u_usg,
            (
                usg_h,
                user,
                bank,
            ),
        )

    def get_usage_weights(self):
        """
        Fetch usage weight config values with fallback defaults.

        Returns:
            tuple: (node_weight, core_weight, gpu_weight) as floats.
        """
        cur = self.conn.cursor()
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
        """Calculate weighted resource usage for one job."""
        weighted_usage = (
            (job.nnodes * node_weight)
            + (job.ncores * core_weight)
            + (job.ngpus * gpu_weight)
        ) * job.elapsed
        return round(weighted_usage, 5)

    def calculate_bank_usage(self, bank):
        # fetch the job_usage value for every user under the passed-in bank
        s_associations = "SELECT job_usage FROM association_table WHERE bank=?"
        job_usage_list = self.conn.execute(s_associations, (bank,)).fetchall()

        total_usage = 0.0
        if job_usage_list:
            # aggregate job usage for bank
            for job_usage in job_usage_list:
                total_usage += job_usage[0]

        # update the bank_table with the total job usage for the bank
        u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
        self.conn.execute(
            u_job_usage,
            (
                total_usage,
                bank,
            ),
        )

        return total_usage

    def calc_bank_usage_tree(self, bank):
        # find all sub-banks of the current bank
        sub_banks = self.conn.execute(
            "SELECT bank FROM bank_table WHERE parent_bank=?", (bank,)
        ).fetchall()

        total_usage = 0.0
        if len(sub_banks) == 0:
            # we've reached a bank with no sub banks, so take the usage from that
            # bank and add it to the total usage for the parent bank
            total_usage = self.calculate_bank_usage(bank)
        else:
            # for each sub bank, keep traversing to find the usage for
            # each bank with users in it
            for sub_bank in sub_banks:
                sub_usage = self.calc_bank_usage_tree(sub_bank[0])
                total_usage += sub_usage

        # update the usage for this bank itself
        u_job_usage = "UPDATE bank_table SET job_usage=? WHERE bank=?"
        self.conn.execute(u_job_usage, (total_usage, bank))

        return total_usage

    def calculate_project_usage(
        self, job_records, node_weight, core_weight, gpu_weight
    ):
        """Calculate weighted usage grouped by project."""
        project_usage = defaultdict(float)
        for job in job_records:
            project_usage[job.project] += self.calculate_weighted_usage(
                job,
                node_weight,
                core_weight,
                gpu_weight,
            )

        return project_usage

    def update_project_usage(
        self,
        job_records,
        node_weight,
        core_weight,
        gpu_weight,
    ):
        """Add weighted usage from newly completed jobs to registered projects."""
        project_usage = self.calculate_project_usage(
            job_records,
            node_weight,
            core_weight,
            gpu_weight,
        )

        self.conn.executemany(
            "UPDATE project_table SET usage=usage+? WHERE project=?",
            [(usage, project) for project, usage in project_usage.items()],
        )

    def update_project_usage_state(self, job_rows):
        """Advance each project's checkpoint to its newest selected job."""
        project_timestamps = defaultdict(float)
        for row in job_rows:
            project = row[8]
            project_timestamps[project] = max(project_timestamps[project], row[4])

        self.conn.executemany(
            """
            UPDATE project_usage_state SET last_job_timestamp=? WHERE project=?
            """,
            [(timestamp, project) for project, timestamp in project_timestamps.items()],
        )
