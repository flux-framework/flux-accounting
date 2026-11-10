/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include "src/plugins/accounting.hpp"
#include "src/common/libtap/tap.h"

static Job make_job ()
{
    Job job;

    job.resources["node"] = 2;
    job.resources["core"] = 8;
    return job;
}


static bool empty_usage (const Association &assoc)
{
    if (assoc.cur_active_jobs || assoc.cur_run_jobs || assoc.cur_sched_jobs
        || assoc.cur_nodes || assoc.cur_cores)
        return false;
    for (const auto &entry : assoc.queue_usage) {
        const QueueUsage &queue = entry.second;

        if (queue.cur_run_jobs || queue.cur_nodes || queue.cur_sched_jobs
            || queue.cur_sched_nodes || queue.cur_sched_cores)
            return false;
    }
    return true;
}


static void test_active_charge_lifecycle ()
{
    Association first = {};
    Association second = {};
    Job job = make_job ();

    ok (job.charge_active (&first), "first active charge succeeds");
    ok (first.cur_active_jobs == 1, "first association owns active charge");
    ok (!job.charge_active (&first), "repeated active charge is a no-op");
    ok (!job.charge_active (&second),
        "charging another association requires a move");
    ok (first.cur_active_jobs == 1 && second.cur_active_jobs == 0,
        "failed charges do not change active counts");
    ok (job.release_active (), "active charge is released");
    ok (!job.release_active (), "repeated active release is a no-op");
    ok (empty_usage (first) && empty_usage (second),
        "active lifecycle leaves associations empty");
}


static void test_active_moves ()
{
    Association first = {};
    Association second = {};
    Job one = make_job ();
    Job two = make_job ();

    one.charge_active (&first);
    two.charge_active (&first);
    ok (first.cur_active_jobs == 2, "multiple jobs contribute to active usage");
    ok (one.move_usage (&second, "debug"),
        "active usage moves to another association");
    ok (first.cur_active_jobs == 1 && second.cur_active_jobs == 1,
        "only the selected job moves");
    ok (!one.move_usage (&second, "batch"),
        "queue-only move does not move active usage");
    ok (first.cur_active_jobs == 1 && second.cur_active_jobs == 1,
        "queue-only move preserves active counts");
    ok (!one.move_usage (&second, "batch"), "repeated move is a no-op");
    one.release_active ();
    two.release_active ();
    ok (empty_usage (first) && empty_usage (second),
        "moved jobs release their recorded owners");
}


static void test_bank_move ()
{
    Association first = {};
    Association second = {};
    Job job = make_job ();

    first.bank_name = "A";
    second.bank_name = "B";
    job.charge_active (&first);
    job.charge_sched (&first, "batch");

    ok (job.move_usage (&second, "batch"),
        "usage moves between banks without a queue change");
    ok (empty_usage (first), "bank move releases usage from bank A");
    ok (second.cur_active_jobs == 1 && second.cur_sched_jobs == 1,
        "bank B receives active and SCHED job usage");
    ok (second.queue_usage["batch"].cur_sched_nodes == 2
        && second.queue_usage["batch"].cur_sched_cores == 8,
        "bank B receives SCHED resources in the existing queue");

    job.release_active ();
    job.release_sched_jobs ();
    job.release_sched_resources ();
    ok (empty_usage (second), "moved bank usage releases cleanly");
}


/*
 * SCHED accounting records a snapshot of the resources held when the charge
 * is created. Change the Job's current resources after charging it, then move
 * its active and SCHED usage together. The destination must receive the
 * original two-node, eight-core charge rather than the updated values, or the
 * transfer and later release would leave the association counters unbalanced.
 */
static void test_combined_usage_moves ()
{
    Association first = {};
    Association second = {};
    Job job = make_job ();

    job.charge_active (&first);
    job.charge_sched (&first, "batch");
    job.resources["node"] = 20;
    job.resources["core"] = 80;
    ok (job.move_usage (&second, "debug"),
        "active and SCHED usage move together");
    ok (empty_usage (first), "move releases all usage from old association");
    ok (second.cur_active_jobs == 1 && second.cur_sched_jobs == 1
        && second.queue_usage["debug"].cur_sched_nodes == 2
        && second.queue_usage["debug"].cur_sched_cores == 8,
        "move preserves the charged SCHED resource snapshot");

    job.release_sched_jobs ();
    ok (job.move_usage (&first, "batch"),
        "partially released SCHED usage moves with active usage");
    ok (empty_usage (second), "partial move clears previous owner and queue");
    ok (first.cur_active_jobs == 1 && first.cur_sched_jobs == 0
        && first.queue_usage["batch"].cur_sched_nodes == 2
        && first.queue_usage["batch"].cur_sched_cores == 8,
        "partial move does not recreate released SCHED job usage");
    job.release_active ();
    job.release_sched_resources ();
    ok (empty_usage (first), "combined usage releases cleanly");
}


static void test_move_without_usage ()
{
    Association first = {};
    Association second = {};
    Job job = make_job ();

    job.charge_active (&first);
    job.release_active ();
    ok (!job.move_usage (&second, "debug"),
        "moving an uncharged job does not invent usage");
    ok (job.queue == "debug", "uncharged move still updates job queue");
    ok (empty_usage (first) && empty_usage (second),
        "uncharged move leaves associations empty");
    ok (first.cur_run_jobs == 0 && second.cur_run_jobs == 0,
        "active accounting does not alter running counts");
}


int main (int argc, char *argv[])
{
    plan (NO_PLAN);
    test_active_charge_lifecycle ();
    test_active_moves ();
    test_bank_move ();
    test_combined_usage_moves ();
    test_move_without_usage ();
    done_testing ();
    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
