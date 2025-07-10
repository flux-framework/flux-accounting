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
    user1.max_run_jobs = 1;
    user1.max_active_jobs = 2;
    user1.queues = {"bronze", "silver", "gold"};

    users[50001]["bank_A"] = user1;
}


/*
 * helper function to add test queues to the queues map
 */
void initialize_queues () {
    queues["bronze"] = {};
    queues["bronze"].max_running_jobs = 3;
    queues["silver"] = {};
    queues["silver"].max_running_jobs = 2;
    queues["gold"] = {};
    queues["gold"].max_running_jobs = 1;
}


/*
 * Scenario 1: The association has the following limit configuration:
 *
 * max_run_jobs: 1
 * max_active_jobs: 2
 *
 * So, a second submitted job cannot run until the currently running one
 * completes. The second submitted job will have the per-association max
 * running jobs limit added to it.
 */
void max_run_jobs_per_association ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 1;
    a->cur_active_jobs = 2;

    // add held Job to Association object
    Job job;
    job.id = 1;
    job.add_dep (D_ASSOC_MRJ);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "association has one held job due to per-association "
        "max_run_jobs limit");
    ok (job.deps.size () == 1,
        "held job has one dependency added to it");
}


// The check to see if the association is under their per-association max
// running jobs limit will return false since cur_run_jobs == 1.
void under_max_run_jobs_per_association_false ()
{
    Association *a = &users[50001]["bank_A"];

    ok (a->under_max_run_jobs () == false,
        "association still has a running job");
}


// When the currently running job completes and the cur_run_jobs counter is
// decremented, the check to see if they are under their max_run_jobs limit
// will return true since now cur_run_jobs == 0. So, the held job can have
// its dependency removed.
void under_max_run_jobs_per_association_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_active_jobs = 1;
    Job held_job = a->held_jobs.front ();

    ok (a->under_max_run_jobs () == true,
        "association is now under max_run_jobs limit");

    // check that held job contains the max-run-jobs per-association limit
    ok (held_job.contains_dep (D_ASSOC_MRJ) == true,
        "held job contains a max running jobs per-association limit");
    ok (held_job.contains_dep (D_QUEUE_MRJ) == false,
        "held job does not contain a max running jobs per-queue limit");

    held_job.remove_dep (D_ASSOC_MRJ);
    // check that held job no longer contains any dependencies
    ok (held_job.deps.size () == 0,
        "held job has no dependencies associated with it");

    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}


/*
 * Scenario 2: The association has the following limit configuration:
 *
 * max_run_jobs: 1
 * max_active_jobs: 2
 *
 * The queue that they are submitting jobs to has the following limit:
 *
 * max_running_jobs: 1
 *
 * A second submitted job to the queue will have *both* the per-association
 * max-run-jobs and the per-queue max-run-jobs limits added to it.
 */
void max_run_jobs_per_queue_and_per_association ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 1;
    a->cur_active_jobs = 2;
    a->queue_usage["gold"].cur_run_jobs = 1; // one running job in gold queue

    // add held Job to Association object
    Job job;
    job.id = 2;
    job.queue = "gold";
    job.add_dep (D_ASSOC_MRJ);
    job.add_dep (D_QUEUE_MRJ);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "asociation has one held job due to max-run-jobs per-association and "
        "per-queue limits");
    ok (job.deps.size () == 2,
        "held job has max-run-jobs per-association and per-queue dependencies "
        "added to it");
}


// Since the association has a limit of just 1 max running job *and* the gold
// queue has a limit of just 1 max running job, the checks to see if the
// association is under *either* their per-association or per-queue
// max-run-jobs limits are false.
void under_max_run_jobs_per_association_and_per_queue_false ()
{
    Association *a = &users[50001]["bank_A"];
    Job held_job = a->held_jobs.front ();
    ok (a->under_max_run_jobs () == false,
        "association still has a running job");
    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == false,
        "association still has a running job in gold queue");
}


// Once a currently running job completes and cur_run_jobs counters for both
// the association's overall cur_run_jobs count and its cur_run_jobs count for
// the queue are decremented, the checks to see if the association is under
// their limits are now true.
void under_max_run_jobs_per_association_and_per_queue_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_active_jobs = 1;
    a->queue_usage["gold"].cur_run_jobs = 0;
    Job held_job = a->held_jobs.front ();

    ok (a->under_max_run_jobs () == true,
        "association is now under max-run-jobs per-association limit");
    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == true,
        "association is now under max-run-jobs per-queue limit");

    // check that held job contains both limits
    ok (held_job.contains_dep (D_ASSOC_MRJ) == true,
        "held job contains a max running jobs per-association limit");
    ok (held_job.contains_dep (D_QUEUE_MRJ) == true,
        "held job contains a max running jobs per-queue limit");

    held_job.remove_dep (D_ASSOC_MRJ);
    held_job.remove_dep (D_QUEUE_MRJ);

    // check that held job no longer contains any dependencies
    ok (held_job.deps.size () == 0,
        "held job has no dependencies associated with it");

    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}


/*
 * Scenario 3: The association has the following limit configuration:
 *
 * max_run_jobs: 10
 * max_active_jobs: 1000
 *
 * The queue that they are submitting jobs to has the following limit:
 *
 * max_running_jobs: 1
 *
 * A second submitted job to the queue will have *just* the per-queue
 * max-run-jobs limit added to it.
 */
void max_run_jobs_per_queue ()
{
    Association *a = &users[50001]["bank_A"];
    a->max_active_jobs = 1000;
    a->max_run_jobs = 10;
    a->cur_run_jobs = 1;
    a->cur_active_jobs = 2;
    a->queue_usage["gold"].cur_run_jobs = 1;

    // add held Job to Association object
    Job job;
    job.id = 3;
    job.queue = "gold";
    job.add_dep (D_QUEUE_MRJ);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "second job gets held due to max-run-jobs per-queue limit");
    ok (job.deps.size () == 1,
        "held job has max-run-jobs per-queue dependency added to it");
}


// The check to see if the association is under their per-queue max running
// jobs limit will return false since cur_run_jobs for this queue == 1.
void under_max_run_jobs_per_queue_false ()
{
    Association *a = &users[50001]["bank_A"];
    Job held_job = a->held_jobs.front ();

    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == false,
        "association still has a running job in gold queue");
}


// Once a currently running job completes and cur_run_jobs counters are
// decremented, the checks to see if the association is under their max running
// jobs limit for the queue is now true.
void under_max_run_jobs_per_queue_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_active_jobs = 1;
    a->queue_usage["gold"].cur_run_jobs = 0;
    Job held_job = a->held_jobs.front ();

    ok (a->under_max_run_jobs () == true,
        "association now under max-run-jobs per-association limit");
    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == true,
        "association now under max-run-jobs per-queue limit");

    // check that held job contains both limits
    ok (held_job.contains_dep (D_ASSOC_MRJ) == false,
        "held job does not contain a max running jobs per-association limit");
    ok (held_job.contains_dep (D_QUEUE_MRJ) == true,
        "held job contains a max running jobs per-queue limit");

    held_job.remove_dep (D_QUEUE_MRJ);

    // check that held job no longer contains any dependencies
    ok (held_job.deps.size () == 0,
        "held job has no dependencies associated with it");

    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}


/*
 * Scenario 4: The association has the following limit configuration:
 *
 * max_run_jobs: 10
 * max_active_jobs: 1000
 * max_nodes: 1
 * max_cores: 2
 *
 * The first job submitted will take up all available resources for that
 * association. Any other subsequently-submitted jobs will have a max-resources
 * per-association limit applied to it.
 */
void max_resources_per_association ()
{
    Association *a = &users[50001]["bank_A"];
    a->max_active_jobs = 1000;
    a->max_run_jobs = 10;
    a->cur_run_jobs = 1;
    a->cur_active_jobs = 2;

    a->max_nodes = 1;
    a->max_cores = 2;
    a->cur_nodes = 1;
    a->cur_cores = 2;

    // add held Job to Association object
    Job job;
    job.id = 4;
    job.ncores = 1;
    job.nnodes = 1;
    job.add_dep (D_ASSOC_MRES);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "second job gets held due to max-resources per-association limit");
    ok (job.deps.size () == 1,
        "held job has max-resources per-association dependency added to it");
}


// The check to see if the association is under their per-association max
// resources limit will return false since the held job would put the
// association over both their max_cores and their max_nodes limits.
void under_max_resources_per_association_false ()
{
    Association *a = &users[50001]["bank_A"];
    Job held_job = a->held_jobs.front ();

    ok (a->under_max_resources (held_job) == false,
        "association is still at max resources");
}


// Once a currently running job completes and cur_nodes and cur_cores counters
// are decremented, the checks to see if the association is under their max
// resources limit for the queue is now true.
void under_max_resources_per_association_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_active_jobs = 1;
    a->cur_nodes = 0;
    a->cur_cores = 0;
    Job held_job = a->held_jobs.front ();

    ok (held_job.nnodes == 1, "held job is requesting one node");
    ok (held_job.ncores == 1, "held job is requesting one core");

    ok (a->under_max_run_jobs () == true,
        "association is under max-run-jobs per-association limit");
    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == true,
        "association is under max-run-jobs per-queue limit");
    ok (a->under_max_resources (held_job) == true,
        "association is under max-resources per-association limit");

    // check that held job contains JUST max-resources per-association limit
    ok (held_job.contains_dep (D_ASSOC_MRJ) == false,
        "held job does not contain a max running jobs per-association limit");
    ok (held_job.contains_dep (D_QUEUE_MRJ) == false,
        "held job does not contain a max running jobs per-queue limit");
    ok (held_job.contains_dep (D_ASSOC_MRES) == true,
        "held job contains a max resources per-association limit");

    held_job.remove_dep (D_ASSOC_MRES);

    // check that held job no longer contains any dependencies
    ok (held_job.deps.size () == 0,
        "held job has no dependencies associated with it");

    // erase held job from association's held_jobs vector
    a->held_jobs.clear ();
    ok (a->held_jobs.size () == 0,
        "association has no more held jobs");
}


/*
 * Scenario 5: The association has the following limit configuration:
 *
 * max_run_jobs: 10
 * max_active_jobs: 1000
 * max_nodes: 1
 * max_cores: 2
 *
 * The first job submitted will take up SOME of the available resources for
 * that association. Any other subsequently-submitted jobs will have a
 * max-resources per-association limit applied to it.
 */
void max_resources_per_association_partial ()
{
    Association *a = &users[50001]["bank_A"];
    a->max_active_jobs = 1000;
    a->max_run_jobs = 10;
    a->cur_run_jobs = 1;
    a->cur_active_jobs = 2;

    a->max_nodes = 1;
    a->max_cores = 4;
    a->cur_nodes = 1;
    a->cur_cores = 2;

    // add held Job to Association object
    Job job;
    job.id = 5;
    job.ncores = 4;
    job.nnodes = 1;
    job.add_dep (D_ASSOC_MRES);
    a->held_jobs.emplace_back (job);

    ok (a->held_jobs.size () == 1,
        "second job gets held due to max-resources per-association limit");
    ok (job.deps.size () == 1,
        "held job has max-resources per-association dependency added to it");
}


// The check to see if the association is under their per-association max
// resources limit will return false since the held job would put the
// association over their max_nodes limit.
void under_max_resources_per_association_partial_false ()
{
    Association *a = &users[50001]["bank_A"];
    Job held_job = a->held_jobs.front ();

    ok (a->under_max_resources (held_job) == false,
        "association is still at max resources");
}


// Once a currently running job completes and cur_nodes and cur_cores counters
// are decremented, the checks to see if the association is under their max
// resources limit for the queue is now true.
void under_max_resources_per_association_partial_true ()
{
    Association *a = &users[50001]["bank_A"];
    a->cur_run_jobs = 0;
    a->cur_active_jobs = 1;
    a->cur_nodes = 0;
    a->cur_cores = 0;
    Job held_job = a->held_jobs.front ();

    ok (held_job.nnodes == 1, "held job is requesting one node");
    ok (held_job.ncores == 4, "held job is requesting four cores");

    ok (a->under_max_run_jobs () == true,
        "association is under max-run-jobs per-association limit");
    ok (a->under_queue_max_run_jobs (held_job.queue, queues) == true,
        "association is under max-run-jobs per-queue limit");
    ok (a->under_max_resources (held_job) == true,
        "association is under max-resources per-association limit");

    // check that held job contains JUST max-resources per-association limit
    ok (held_job.contains_dep (D_ASSOC_MRJ) == false,
        "held job does not contain a max running jobs per-association limit");
    ok (held_job.contains_dep (D_QUEUE_MRJ) == false,
        "held job does not contain a max running jobs per-queue limit");
    ok (held_job.contains_dep (D_ASSOC_MRES) == true,
        "held job contains a max resources per-association limit");

    held_job.remove_dep (D_ASSOC_MRES);

    // check that held job no longer contains any dependencies
    ok (held_job.deps.size () == 0,
        "held job has no dependencies associated with it");

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

    max_run_jobs_per_association ();
    under_max_run_jobs_per_association_false ();
    under_max_run_jobs_per_association_true ();

    max_run_jobs_per_queue_and_per_association ();
    under_max_run_jobs_per_association_and_per_queue_false ();
    under_max_run_jobs_per_association_and_per_queue_true ();

    max_run_jobs_per_queue ();
    under_max_run_jobs_per_queue_false ();
    under_max_run_jobs_per_queue_true ();

    max_resources_per_association ();
    under_max_resources_per_association_false ();
    under_max_resources_per_association_true ();

    max_resources_per_association_partial ();
    under_max_resources_per_association_partial_false ();
    under_max_resources_per_association_partial_true ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
