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
}

void queue_limits_defined ()
{
    ok (queues["bronze"].max_nodes_per_assoc == 1,
        "bronze queue has a max_nodes limit of 1");
}

/*
 * Without running any prior jobs, an association is under the
 * queue's max_nodes limit.
 */
void association_under_queue_max_nodes_limit_true ()
{
    Association *a = &users[50001]["bank_A"];

    // create a Job object
    Job job;
    job.id = 1;
    job.nnodes = 1;
    job.queue = "bronze";

    ok (a->queue_usage["bronze"].cur_nodes == 0,
        "association has no occupied nodes under bronze queue");
    ok (a->under_queue_max_resources (job, queues["bronze"]) == true,
        "association is under queue's max_nodes limit");

    // assume job passes all checks and has moved to RUN state
    a->cur_run_jobs = 1;
    a->cur_nodes = 1;
    a->queue_usage["bronze"].cur_run_jobs = 1;
    a->queue_usage["bronze"].cur_nodes = 1;
}

/*
 * Once an association's limit is hit within a particular queue, a
 * per-queue dependency is added on the job.
 */
void association_under_queue_max_nodes_limit_false ()
{
    Association *a = &users[50001]["bank_A"];

    // assume Job object above is still running; create a Job object that is
    // also under the "bronze" queue (so it will have a dependency added to it)
    Job job;
    job.id = 2;
    job.nnodes = 1;
    job.queue = "bronze";
    job.add_dep (D_QUEUE_MRES);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "association has one held job due to per-queue max_resources limit");
    ok (job.deps.size () == 1,
        "held job has one dependency added to it");
    ok (a->under_queue_max_resources (job, queues["bronze"]) == false,
        "association is not under queue's max_nodes limit");
}

/*
 * Once the first job finishes running and current job and resource counters
 * are decremented, the check for the held job will pass, the dependency will
 * be removed, and the job can proceed to RUN state.
 */
void association_release_held_job_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_nodes = 0;
    a->queue_usage["bronze"].cur_run_jobs = 0;
    a->queue_usage["bronze"].cur_nodes = 0;
    Job held_job = a->held_jobs.front ();

    ok (a->under_queue_max_resources (held_job, queues["bronze"]) == true,
        "association is now under queue's max_nodes limit");
    
    held_job.remove_dep (D_QUEUE_MRES);
    ok (held_job.deps.size () == 0,
        "held job no longer has any dependencies added to it");
    
    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}

int main (int argc, char* argv[])
{
    // add an association
    initialize_map (users);
    // add queues to the test queues map
    initialize_queues ();

    queue_limits_defined ();
    association_under_queue_max_nodes_limit_true ();
    association_under_queue_max_nodes_limit_false ();
    association_release_held_job_true ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
