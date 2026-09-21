###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
DB_SCHEMA_VERSION = 39

# flux-accounting DB table column names
ASSOCIATION_TABLE = [
    "creation_time",
    "mod_time",
    "active",
    "username",
    "userid",
    "bank",
    "default_bank",
    "shares",
    "job_usage",
    "fairshare",
    "max_running_jobs",
    "max_active_jobs",
    "max_nodes",
    "max_cores",
    "queues",
    "projects",
    "default_project",
    "max_sched_jobs",
]
BANK_TABLE = [
    "bank_id",
    "bank",
    "active",
    "parent_bank",
    "shares",
    "job_usage",
    "priority",
    "ignore_older_than",
]
QUEUE_TABLE = [
    "queue",
    "min_nodes_per_job",
    "max_nodes_per_job",
    "max_time_per_job",
    "priority",
    "max_running_jobs",
    "max_nodes_per_assoc",
    "max_sched_jobs",
    "max_sched_nodes_per_assoc",
    "max_sched_cores_per_assoc",
    "max_nodes",
    "max_cores",
]
PROJECT_TABLE = ["project_id", "project", "usage"]
PROJECT_USAGE_STATE_TABLE = ["project", "last_job_timestamp"]
JOBS_TABLE = [
    "id",
    "userid",
    "t_submit",
    "t_run",
    "t_inactive",
    "ranks",
    "R",
    "jobspec",
    "project",
    "bank",
    "requested_duration",
    "actual_duration",
]
PRIORITY_FACTOR_WEIGHTS_TABLE = ["factor", "weight"]
CONFIG_TABLE = ["key", "value"]
JOB_USAGE_PER_ASSOC_TABLE = [
    "username",
    "userid",
    "bank",
    "period",
    "value",
]
