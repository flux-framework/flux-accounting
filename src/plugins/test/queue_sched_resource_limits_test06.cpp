/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
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

#include <iostream>
#include <fstream>
#include <vector>
#include <map>
#include <string>

#include "src/plugins/accounting.hpp"
#include "src/plugins/job.hpp"
#include "src/common/libtap/tap.h"

// define a test users map to run tests on
std::map<int, std::map<std::string, Association>> users;
// define a test queues map
std::map<std::string, Queue> queues;
// define the live per-queue total sched nodes/cores maps, mirroring the
// globals in mf_priority.cpp; these span all associations in a queue
std::map<std::string, int> queue_total_sched_nodes;
std::map<std::string, int> queue_total_sched_cores;
bool deny_unknown_queues = false;


/*
 * add two associations under the same queue
 */
void initialize_map (
    std::map<int, std::map<std::string, Association>> &users)
{
    Association user1 {};
    user1.bank_name = "bank_A";
    user1.max_run_jobs = 100;
    user1.max_active_jobs = 150;
    user1.queues = {"bronze"};
    users[50001]["bank_A"] = user1;

    Association user2 {};
    user2.bank_name = "bank_A";
    user2.max_run_jobs = 100;
    user2.max_active_jobs = 150;
    user2.queues = {"bronze"};
    users[50002]["bank_A"] = user2;
}

/*
 * helper function to add a test queue with a queue-wide total limit
 */
void initialize_queues () {
    queues["bronze"] = {};
    queues["bronze"].name = "bronze";
    queues["bronze"].max_nodes = 4;
    queues["bronze"].max_cores = 4;
}

void queue_total_limits_defined ()
{
    ok (queues["bronze"].max_nodes == 4,
        "bronze queue has a max_nodes total limit of 4");
    ok (queues["bronze"].max_cores == 4,
        "bronze queue has a max_cores total limit of 4");
}

/*
 * With no jobs in SCHED state, a job fits under the queue-wide total limit.
 */
void under_queue_total_limit_true ()
{
    Job job;
    job.id = 1;
    job.nnodes = 4;
    job.ncores = 4;
    job.queue = "bronze";

    ok (queue_total_sched_nodes["bronze"] == 0,
        "queue has no nodes in SCHED state across associations");
    ok (under_queue_total_max_nodes (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_nodes) == true,
        "job is under queue's total max_nodes limit");
    ok (under_queue_total_max_cores (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_cores) == true,
        "job is under queue's total max_cores limit");

    // assume the job (from user 50001) enters SCHED state, consuming all
    // queue-wide headroom
    queue_total_sched_nodes["bronze"] += job.nnodes;
    queue_total_sched_cores["bronze"] += job.ncores;
}

/*
 * A second association's job in the same queue is now over the shared total
 * limit even though that association has run no jobs of its own.
 */
void under_queue_total_limit_false_across_assoc ()
{
    Job job;
    job.id = 2;
    job.nnodes = 1;
    job.ncores = 1;
    job.queue = "bronze";

    ok (under_queue_total_max_nodes (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_nodes) == false,
        "second association's job exceeds queue's total max_nodes limit");
    ok (under_queue_total_max_cores (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_cores) == false,
        "second association's job exceeds queue's total max_cores limit");
}

/*
 * When the first association's job leaves SCHED state and the counter is
 * decremented, headroom returns and the held job can be released.
 */
void headroom_returns_after_inactive ()
{
    // first association's 4-node/4-core job goes INACTIVE
    queue_total_sched_nodes["bronze"] -= 4;
    queue_total_sched_cores["bronze"] -= 4;

    Job job;
    job.id = 2;
    job.nnodes = 1;
    job.ncores = 1;
    job.queue = "bronze";

    ok (under_queue_total_max_nodes (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_nodes) == true,
        "held job is under queue's total max_nodes limit again");
    ok (under_queue_total_max_cores (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_cores) == true,
        "held job is under queue's total max_cores limit again");
}

/*
 * The "pending" overload reserves headroom for jobs released earlier in a
 * check_and_release_held_jobs () pass that have not yet bumped the global
 * counter, so a subsequent held job sees the correct remaining headroom.
 */
void pending_offset_reserves_headroom ()
{
    // queue currently has 2 nodes/cores in SCHED state; limit is 4
    queue_total_sched_nodes["bronze"] = 2;
    queue_total_sched_cores["bronze"] = 2;

    Job job;
    job.id = 3;
    job.nnodes = 2;
    job.ncores = 2;
    job.queue = "bronze";

    // with no pending offset, the job fits exactly (2 + 2 == 4)
    ok (under_queue_total_max_nodes (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_nodes,
                                     0) == true,
        "job fits with no pending offset");
    // but if a prior held job in this pass already reserved 1 node/core, the
    // job no longer fits (2 + 2 + 1 > 4)
    ok (under_queue_total_max_nodes (job,
                                     "bronze",
                                     queues,
                                     queue_total_sched_nodes,
                                     1) == false,
        "job does not fit once pending offset is applied");
}

/*
 * If the queue cannot be found in the queues map, the check is skipped and
 * returns true (unlimited), matching the per-assoc behavior.
 */
void unknown_queue_is_unlimited ()
{
    Job job;
    job.id = 4;
    job.nnodes = 1000;
    job.ncores = 1000;
    job.queue = "nonexistent";

    ok (under_queue_total_max_nodes (job,
                                     "nonexistent",
                                     queues,
                                     queue_total_sched_nodes) == true,
        "unknown queue is treated as unlimited");
}

int main (int argc, char* argv[])
{
    // add associations
    initialize_map (users);
    // add queues to the test queues map
    initialize_queues ();

    queue_total_limits_defined ();
    under_queue_total_limit_true ();
    under_queue_total_limit_false_across_assoc ();
    headroom_returns_after_inactive ();
    pending_offset_reserves_headroom ();
    unknown_queue_is_unlimited ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
