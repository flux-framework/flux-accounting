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
"""Completed-job usage with elapsed-time continuous decay."""

import logging
import sqlite3
import time
from collections import defaultdict

from fluxacct.jobs import records as j
from fluxacct.jobs.calculators.base import (
    get_new_job_rows,
    calculate_weighted_usage,
    calc_bank_usage_tree,
    get_new_project_job_rows,
    get_usage_weights,
    JobUsageCalculator,
    update_project_usage,
    update_project_usage_state,
)

LOGGER = logging.getLogger("fluxacct.jobs.usage")


def retention_factor(elapsed, half_life, decay_factor):
    """Return the fraction of old usage retained after elapsed seconds."""
    if elapsed < 0.0:
        raise ValueError("elapsed time must not be negative")
    if half_life <= 0.0:
        raise ValueError("priority_decay_half_life must be greater than 0")
    if not 0.0 < decay_factor < 1.0:
        raise ValueError("decay_factor must be between 0 and 1")
    return decay_factor ** (elapsed / half_life)


class ContinuousDecayCalculator(JobUsageCalculator):
    """Job-usage calculation strategy using elapsed-time decay."""

    @staticmethod
    def _get_config_float(cur, key, default):
        row = cur.execute(
            "SELECT value FROM config_table WHERE key=?", (key,)
        ).fetchone()
        return float(row[0]) if row is not None else default

    @staticmethod
    def _last_update(cur, now):
        row = cur.execute(
            "SELECT last_update FROM usage_decay_state WHERE cluster='cluster'"
        ).fetchone()
        if row is not None:
            return float(row[0]), False
        cur.execute(
            "INSERT INTO usage_decay_state (cluster, last_update) VALUES (?, ?)",
            ("cluster", now),
        )
        return now, True

    @staticmethod
    def _update_timestamps(cur, association_timestamps):
        cur.executemany(
            """
            UPDATE job_usage_factor_table SET last_job_timestamp=?
            WHERE userid=? AND bank=?
            """,
            [
                (timestamp, userid, bank)
                for (userid, bank), timestamp in association_timestamps.items()
            ],
        )

    @staticmethod
    def _update_association_usage(cur, retention, contributions):
        cur.execute(
            "UPDATE association_table SET job_usage=job_usage * ?",
            (retention,),
        )
        cur.executemany(
            """
            UPDATE association_table SET job_usage=job_usage+?
            WHERE userid=? AND bank=?
            """,
            [(usage, userid, bank) for (userid, bank), usage in contributions.items()],
        )

    def update(self):
        LOGGER.info(
            "beginning job-usage update for flux-accounting DB; "
            "slow response times may occur"
        )
        now = time.time()
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()

        with self.conn:
            last_update, initialized = self._last_update(cur, now)
            if initialized:
                LOGGER.info(
                    "initialized continuous job usage decay state; "
                    "usage will be updated on the next run"
                )
                return 0
            if now <= last_update:
                LOGGER.info("continuous job usage is already current")
                return 0

            node_weight, core_weight, gpu_weight = get_usage_weights(cur)
            half_life = self._get_config_float(
                cur, "priority_decay_half_life", 604800.0
            )
            decay_factor = self._get_config_float(cur, "decay_factor", 0.5)
            retention = retention_factor(now - last_update, half_life, decay_factor)

            new_jobs = get_new_job_rows(cur)
            new_job_records = j.convert_to_obj(new_jobs)
            new_project_jobs = [
                row for row in get_new_project_job_rows(cur) if row[4] <= now
            ]
            new_project_job_records = j.convert_to_obj(new_project_jobs)

            contributions = defaultdict(float)
            association_timestamps = defaultdict(float)
            for job in new_job_records:
                if job.t_inactive > now:
                    continue
                key = (job.userid, job.bank)
                contributions[key] += calculate_weighted_usage(
                    job,
                    node_weight,
                    core_weight,
                    gpu_weight,
                ) * retention_factor(now - job.t_inactive, half_life, decay_factor)
                association_timestamps[key] = max(
                    association_timestamps[key], job.t_inactive
                )

            self._update_association_usage(cur, retention, contributions)
            self._update_timestamps(cur, association_timestamps)

            s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
            cur.execute(s_root_bank)
            result = cur.fetchall()
            if result:
                calc_bank_usage_tree(cur, result[0][0])

            update_project_usage(
                cur,
                new_project_job_records,
                node_weight,
                core_weight,
                gpu_weight,
            )
            update_project_usage_state(cur, new_project_jobs)

            cur.execute(
                "UPDATE usage_decay_state SET last_update=? WHERE cluster='cluster'",
                (now,),
            )

        LOGGER.info("job-usage update for flux-accounting DB now complete")
        return 0
