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
bool deny_unknown_queues = false;


/*
 * add an association
 */
void initialize_map (
    std::map<int, std::map<std::string, Association>> &users)
{
    Association user1 {};
    user1.bank_name = "bank_A";
    user1.max_run_jobs = 100;
    user1.max_active_jobs = 150;
    user1.queues = {"bronze", "silver"};

    users[50001]["bank_A"] = user1;
}

/*
 * helper function to add test queues to the queues map
 */
void initialize_queues () {
    queues["bronze"] = {};
    queues["bronze"].name = "bronze";
    queues["bronze"].max_running_jobs = 100;
    queues["bronze"].max_nodes_per_assoc = 1;
    queues["bronze"].max_sched_nodes_per_assoc = 1;
}

void queue_limits_defined ()
{
    ok (queues["bronze"].max_nodes_per_assoc == 1,
        "bronze queue has a per-job max_nodes limit of 1");
    ok (queues["bronze"].max_sched_nodes_per_assoc == 1,
        "bronze queue has a max_sched_nodes limit of 1");
}

/*
 * Without any SCHED/RUN commitments, an association is under the
 * queue's max_sched_nodes limit.
 */
void association_under_queue_max_sched_nodes_limit_true ()
{
    Association *a = &users[50001]["bank_A"];

    // create a Job object
    Job job;
    job.id = 1;
    job.resources["node"] = 1;
    job.queue = "bronze";

    ok (a->queue_usage["bronze"].cur_nodes == 0,
        "association has no occupied nodes under bronze queue");
    ok (a->under_queue_max_sched_nodes (job, "bronze", queues) == true,
        "association is under queue's max_sched_nodes limit");

    // assume job passes all checks and has moved to RUN state
    a->cur_run_jobs = 1;
    a->cur_nodes = 1;
    a->queue_usage["bronze"].cur_run_jobs = 1;
    a->queue_usage["bronze"].cur_nodes = 1;
}

/*
 * Once an association's sched-node limit is hit within a particular queue, a
 * per-queue dependency is added on the job.
 */
void association_under_queue_max_sched_nodes_limit_false ()
{
    Association *a = &users[50001]["bank_A"];
    a->queue_usage["bronze"].cur_sched_nodes = 1;

    // assume Job object above is still running; create a Job object that is
    // also under the "bronze" queue (so it will have a dependency added to it)
    Job job;
    job.id = 2;
    job.resources["node"] = 1;
    job.queue = "bronze";
    job.add_dep (D_QUEUE_MSN);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "association has one held job due to per-queue max_sched_nodes limit");
    ok (job.deps.size () == 1,
        "held job has one dependency added to it");
    ok (a->under_queue_max_sched_nodes (job, "bronze", queues) == false,
        "association is not under queue's max_sched_nodes limit");
}

/*
 * Once the first job finishes and sched-node counters are decremented, the
 * check for the held job will pass, the dependency will be removed, and the
 * job can proceed to RUN state.
 */
void association_release_held_sched_node_job_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_nodes = 0;
    a->queue_usage["bronze"].cur_run_jobs = 0;
    a->queue_usage["bronze"].cur_nodes = 0;
    a->queue_usage["bronze"].cur_sched_nodes = 0;
    Job held_job = a->held_jobs.front ();

    ok (a->under_queue_max_sched_nodes (held_job, "bronze", queues) == true,
        "association is now under queue's max_sched_nodes limit");

    held_job.remove_dep (D_QUEUE_MSN);
    ok (held_job.deps.size () == 0,
        "held job no longer has any dependencies added to it");

    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}

/*
 * Jobs released earlier in a held-job sweep count against the per-queue
 * max_sched_nodes limit before their persistent counters are updated.
 */
void pending_sched_nodes_count_against_queue_max ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_nodes = 0;
    a->queue_usage["bronze"].cur_run_jobs = 0;
    a->queue_usage["bronze"].cur_nodes = 0;
    a->queue_usage["bronze"].cur_sched_nodes = 0;

    Job job;
    job.id = 3;
    job.resources["node"] = 1;
    job.queue = "bronze";

    ok (a->under_queue_max_sched_nodes (job, "bronze", queues, 1) == false,
        "pending SCHED-state node counts against per-queue max_sched_nodes");
    ok (a->under_queue_max_sched_nodes (job, "bronze", queues, 0) == true,
        "queue has headroom without pending SCHED commitment");
}

/*
 * A Queue object's max_sched_jobs property can be set and configured.
 */
void set_queue_max_sched_jobs_limit ()
{
    queues["bronze"].max_sched_jobs = 1;
    ok (queues["bronze"].max_sched_jobs == 1,
        "bronze queue has a max_sched_jobs limit of 1");
}

/*
 * If the queue being specified cannot be found, it will be initialized in the
 * queues map with default properties, including max_sched_jobs.
 */
void association_under_queue_max_sched_jobs_default ()
{
    Association *a = &users[50001]["bank_A"];
    ok (a->under_queue_max_sched_jobs ("foo", queues) == true,
        "check returns true when queue cannot be found");

    ok (queues["foo"].max_sched_jobs == 2147483647,
        "queue initialized in queues map with max max_sched_jobs value");
}

/*
 * If an association is under the queue's max_sched_jobs limit,
 * under_queue_max_sched_jobs () will return true.
 */
void association_under_queue_max_sched_jobs_limit_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_active_jobs = 0;
    a->cur_sched_jobs = 0;
    a->queue_usage["bronze"].cur_sched_jobs = 0;

    ok (a->under_queue_max_sched_jobs ("bronze", queues) == true,
        "association is under max_sched_jobs limit");
}

/*
 * If an association is *not* under the queue's max_sched_jobs limit,
 * under_queue_max_sched_jobs () will return false.
 */
void association_under_queue_max_sched_jobs_limit_false ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_active_jobs = 2;
    a->cur_sched_jobs = 1;
    a->queue_usage["bronze"].cur_sched_jobs = 1;

    ok (a->under_queue_max_sched_jobs ("bronze", queues) == false,
        "association is not under max_sched_jobs limit");
}

int main (int argc, char* argv[])
{
    // add an association
    initialize_map (users);
    // add queues to the test queues map
    initialize_queues ();

    queue_limits_defined ();
    association_under_queue_max_sched_nodes_limit_true ();
    association_under_queue_max_sched_nodes_limit_false ();
    association_release_held_sched_node_job_true ();
    pending_sched_nodes_count_against_queue_max ();
    set_queue_max_sched_jobs_limit ();
    association_under_queue_max_sched_jobs_limit_true ();
    association_under_queue_max_sched_jobs_limit_false ();
    association_under_queue_max_sched_jobs_default ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
