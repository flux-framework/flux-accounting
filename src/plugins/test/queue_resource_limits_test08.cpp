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

#include <map>
#include <string>

#include "src/plugins/accounting.hpp"
#include "src/plugins/job.hpp"
#include "src/common/libtap/tap.h"

bool deny_unknown_queues = false;


static Job make_job (const std::string &queue, int nnodes, int ncores)
{
    Job job;

    job.queue = queue;
    job.resources["node"] = nnodes;
    job.resources["core"] = ncores;

    return job;
}


static void test_queue_total_defaults_to_unlimited ()
{
    std::map<std::string, Queue> queues;
    std::map<std::string, int> nodes;
    std::map<std::string, int> cores;
    Job job = make_job ("batch", 1024, 2048);

    queues["batch"].name = "batch";

    ok (under_queue_total_max_nodes (job, "batch", queues, nodes),
        "default queue-total max_nodes is unlimited");
    ok (under_queue_total_max_cores (job, "batch", queues, cores),
        "default queue-total max_cores is unlimited");
}


static void test_queue_total_limits ()
{
    std::map<std::string, Queue> queues;
    std::map<std::string, int> nodes;
    std::map<std::string, int> cores;
    Job job = make_job ("batch", 2, 4);

    queues["batch"].name = "batch";
    queues["batch"].max_nodes = 4;
    queues["batch"].max_cores = 8;

    nodes["batch"] = 2;
    cores["batch"] = 4;
    ok (under_queue_total_max_nodes (job, "batch", queues, nodes),
        "job fits under configured queue-total node limit");
    ok (under_queue_total_max_cores (job, "batch", queues, cores),
        "job fits under configured queue-total core limit");

    nodes["batch"] = 3;
    cores["batch"] = 5;
    ok (!under_queue_total_max_nodes (job, "batch", queues, nodes),
        "job is blocked by configured queue-total node limit");
    ok (!under_queue_total_max_cores (job, "batch", queues, cores),
        "job is blocked by configured queue-total core limit");
}


static void test_unknown_queue_is_unlimited ()
{
    std::map<std::string, Queue> queues;
    std::map<std::string, int> nodes;
    std::map<std::string, int> cores;
    Job job = make_job ("missing", 1, 1);

    nodes["missing"] = 2147483647;
    cores["missing"] = 2147483647;

    ok (under_queue_total_max_nodes (job, "missing", queues, nodes),
        "unknown queue is not blocked by queue-total node limit");
    ok (under_queue_total_max_cores (job, "missing", queues, cores),
        "unknown queue is not blocked by queue-total core limit");
}


static void test_pending_release_counters ()
{
    std::map<std::string, Queue> queues;
    std::map<std::string, int> nodes;
    std::map<std::string, int> cores;
    Job job = make_job ("batch", 2, 4);

    queues["batch"].name = "batch";
    queues["batch"].max_nodes = 4;
    queues["batch"].max_cores = 8;

    nodes["batch"] = 0;
    cores["batch"] = 0;
    ok (under_queue_total_max_nodes (job, "batch", queues, nodes, 2),
        "pending nodes leave room up to the queue-total node limit");
    ok (under_queue_total_max_cores (job, "batch", queues, cores, 4),
        "pending cores leave room up to the queue-total core limit");

    ok (!under_queue_total_max_nodes (job, "batch", queues, nodes, 3),
        "pending nodes can block a release in the same sweep");
    ok (!under_queue_total_max_cores (job, "batch", queues, cores, 5),
        "pending cores can block a release in the same sweep");
}


static void test_inactive_decrement_restores_headroom ()
{
    std::map<std::string, Queue> queues;
    std::map<std::string, int> nodes;
    std::map<std::string, int> cores;
    Job job = make_job ("batch", 2, 4);

    queues["batch"].name = "batch";
    queues["batch"].max_nodes = 4;
    queues["batch"].max_cores = 8;
    nodes["batch"] = 4;
    cores["batch"] = 8;

    ok (!under_queue_total_max_nodes (job, "batch", queues, nodes),
        "full queue-total node limit blocks a job");
    ok (!under_queue_total_max_cores (job, "batch", queues, cores),
        "full queue-total core limit blocks a job");

    nodes["batch"] -= 2;
    cores["batch"] -= 4;
    ok (under_queue_total_max_nodes (job, "batch", queues, nodes),
        "inactive node decrement restores queue-total headroom");
    ok (under_queue_total_max_cores (job, "batch", queues, cores),
        "inactive core decrement restores queue-total headroom");
}


int main (int argc, char* argv[])
{
    test_queue_total_defaults_to_unlimited ();
    test_queue_total_limits ();
    test_unknown_queue_is_unlimited ();
    test_pending_release_counters ();
    test_inactive_decrement_restores_headroom ();

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
