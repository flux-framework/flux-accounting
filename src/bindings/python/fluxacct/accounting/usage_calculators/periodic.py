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
import logging
import sqlite3
import time
from collections import defaultdict

from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting.usage_calculators.base import JobUsageCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


class PeriodicUsageCalculator(JobUsageCalculator):
    """Calculate job usage using periodic bins and half-life decay."""

    def update_last_job_timestamp(self, last_t_inactive, user, bank):
        """Save the most recent inactive-job timestamp for an association."""
        u_ts = """
            UPDATE job_usage_factor_table SET last_job_timestamp=?
            WHERE username=? AND bank=?
            """
        self.conn.execute(u_ts, (last_t_inactive, user, bank))

    def update_current_usage_bin(self, usage, user, bank, userid):
        """Write the current job-usage bin for an association."""
        self.conn.execute(
            """
            INSERT INTO job_usage_per_association_table
                (username, userid, bank, period, value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (username, bank, period)
            DO UPDATE SET value=excluded.value
            """,
            (user, userid, bank, 0, usage),
        )

    def apply_decay_factor(self, user, bank, userid):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM config_table WHERE key='decay_factor'")
        row = cur.fetchone()
        decay = float(row[0]) if row else 0.5

        cur.execute(
            """
            SELECT period, value FROM job_usage_per_association_table
            WHERE username=? AND bank=?
            ORDER BY period DESC
            """,
            (user, bank),
        )
        periods = cur.fetchall()

        for period, value in periods:
            next_period = period + 1
            cur.execute(
                """
                UPDATE job_usage_per_association_table SET value=?
                WHERE username=? AND userid=? AND bank=? AND period=?
                """,
                (value * decay, user, userid, bank, next_period),
            )

        cur.execute(
            """
            UPDATE job_usage_per_association_table SET value=0.0
            WHERE username=? AND userid=? AND bank=? AND period=0
            """,
            (user, userid, bank),
        )

        cur.execute(
            """
            SELECT SUM(value) FROM job_usage_per_association_table
            WHERE username=? AND userid=? AND bank=? AND period > 0
            """,
            (user, userid, bank),
        )
        result = cur.fetchone()
        return result[0] if result[0] is not None else 0.0

    def calculate_usage_factor(
        self,
        pdhl,
        user,
        bank,
        userid,
        end_hl,
        user_jobs,
        node_weight,
        core_weight,
        gpu_weight,
    ):
        cur = self.conn.cursor()

        # fetch all current period values for this association
        cur.execute(
            """
            SELECT period, value FROM job_usage_per_association_table
            WHERE username=? AND bank=?
            ORDER BY period ASC
            """,
            (user, bank),
        )
        period_rows = cur.fetchall()
        usage_factors = [row[1] for row in period_rows]

        # hl_period represents the number of seconds that represent one usage bin
        hl_period = pdhl
        last_t_inactive = 0.0
        usg_current = 0.0

        if len(user_jobs) > 0:
            user_jobs.sort(key=lambda job: job.t_inactive)

            per_job_factors = []
            for job in user_jobs:
                weighted_usage = self.calculate_weighted_usage(
                    job, node_weight, core_weight, gpu_weight
                )
                per_job_factors.append(round(weighted_usage, 5))

            last_t_inactive = user_jobs[-1].t_inactive
            usg_current = sum(per_job_factors)

            self.update_last_job_timestamp(last_t_inactive, user, bank)

        if len(user_jobs) == 0 and (float(end_hl) > (time.time() - hl_period)):
            # no new jobs in the current half-life period; the job usage for the
            # association stays exactly the same
            usg_historical = sum(usage_factors)
        elif len(user_jobs) == 0 and (float(end_hl) < (time.time() - hl_period)):
            # no new jobs in the new half-life period; previous job usage periods need
            # to have a half-life decay applied to them
            usg_historical = self.apply_decay_factor(user, bank, userid)

            self.update_current_usage_bin(usg_current, user, bank, userid)
            self.update_association_usage(usg_historical, user, bank)
        elif (last_t_inactive - float(end_hl)) < hl_period:
            # found new jobs in the current half-life period; we need to 1) add the
            # new jobs to the current usage period, and 2) update the historical usage
            # period
            usg_current += usage_factors[0]
            usg_historical = usg_current + sum(usage_factors[1:])

            self.update_current_usage_bin(usg_current, user, bank, userid)
            self.update_association_usage(usg_historical, user, bank)
        else:
            # found new jobs in the new half-life period
            # apply decay factor to past usage periods of a user's jobs
            usg_past = self.apply_decay_factor(user, bank, userid)
            usg_historical = usg_current + usg_past

            self.update_current_usage_bin(usg_historical, user, bank, userid)
            self.update_association_usage(usg_historical, user, bank)

        return usg_historical

    def advance_half_life_period(self, pdhl):
        hl_period = pdhl
        cur = self.conn.cursor()

        s_end_hl = """
            SELECT end_half_life_period
            FROM t_half_life_period_table
            WHERE cluster='cluster'
            """
        cur.execute(s_end_hl)
        row = cur.fetchone()
        end_hl = row[0]

        if float(end_hl) < (time.time() - hl_period):
            update_timestamp_stmt = """
                UPDATE t_half_life_period_table
                SET end_half_life_period=?
                WHERE cluster='cluster'
                """
            self.conn.execute(update_timestamp_stmt, ((float(end_hl) + hl_period),))

    def update(self) -> int:
        LOGGER.info(
            "beginning job-usage update for flux-accounting DB; "
            "slow response times may occur"
        )
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()

        with self.conn:
            s_end_hl = """
                SELECT end_half_life_period FROM t_half_life_period_table
                WHERE cluster='cluster'
                """
            cur.execute(s_end_hl)
            row = cur.fetchone()
            end_hl = row[0]

            node_weight, core_weight, gpu_weight = self.get_usage_weights(cur)

            self.conn.execute("BEGIN TRANSACTION")
            s_assoc = """
                SELECT a.username, a.userid, a.bank, a.default_bank,
                    j.last_job_timestamp
                FROM association_table a
                LEFT JOIN job_usage_factor_table j
                ON a.username = j.username AND a.bank = j.bank
                """
            cur.execute(s_assoc)
            result = cur.fetchall()

            last_reconfigured = cur.execute(
                "SELECT value FROM config_table WHERE key='reconfigure_time'"
            ).fetchone()
            last_reconfigured = (
                last_reconfigured[0] if last_reconfigured is not None else 0.0
            )

            s_new_jobs = """
                SELECT r.userid,r.id,r.t_submit,r.t_run,r.t_inactive,r.ranks,r.R,
                r.jobspec,r.project,r.bank,r.requested_duration,r.actual_duration,
                b.ignore_older_than
                FROM jobs r LEFT JOIN job_usage_factor_table j
                ON r.userid = j.userid AND r.bank = j.bank
                LEFT JOIN bank_table b
                ON r.bank = b.bank WHERE r.t_inactive > j.last_job_timestamp
                AND r.t_inactive > b.ignore_older_than
                AND r.t_inactive > ?
            """
            cur.execute(s_new_jobs, (last_reconfigured,))
            new_jobs = cur.fetchall()
            new_job_records = j.convert_to_obj(new_jobs)
            association_jobs = defaultdict(list)
            for job in new_job_records:
                key = (job.userid, job.bank)
                association_jobs[key].append(job)

            pdhl = float(
                cur.execute(
                    "SELECT value FROM config_table "
                    "WHERE key='priority_decay_half_life'"
                ).fetchone()[0]
            )

            for row in result:
                self.calculate_usage_factor(
                    pdhl=pdhl,
                    user=row["username"],
                    bank=row["bank"],
                    userid=row["userid"],
                    end_hl=end_hl,
                    user_jobs=association_jobs[(row["userid"], row["bank"])],
                    node_weight=node_weight,
                    core_weight=core_weight,
                    gpu_weight=gpu_weight,
                )

            s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
            cur.execute(s_root_bank)
            result = cur.fetchall()
            parent_bank = result[0][0]

            self.calculate_hierarchical_bank_usage(cur, parent_bank)
            self.advance_half_life_period(pdhl)

            LOGGER.info("job-usage update for flux-accounting DB now complete")

            return 0
