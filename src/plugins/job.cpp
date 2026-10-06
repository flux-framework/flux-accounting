/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include "accounting.hpp"

int Job::count_resources (json_t *jobspec)
{
    jj_counts counts;
    if (jj_get_counts_json (jobspec, counts) < 0)
        return -1;

    // after a successful parse the node, slot, and core keys are
    // guaranteed to be present in the map with counts of at least 1
    resources = counts.counts;
    return 0;
}


void Job::add_dep (const std::string &dep)
{
    deps.push_back (dep);
}


bool Job::contains_dep (const std::string &dep) const
{
    return std::find (deps.begin (), deps.end (), dep) != deps.end ();
}


void Job::remove_dep (const std::string &dep)
{
    deps.erase (std::remove(deps.begin (), deps.end (), dep), deps.end ());
}


bool Job::charge_sched (Association *assoc, const std::string &queue)
{
    if (sched_charge.jobs || sched_charge.resources)
        return false;

    sched_charge.assoc = assoc;
    sched_charge.queue = queue;
    sched_charge.nodes = nnodes ();
    sched_charge.cores = ncores ();
    sched_charge.jobs = true;
    sched_charge.resources = true;
    this->queue = queue;

    assoc->cur_sched_jobs++;
    assoc->queue_usage[queue].cur_sched_jobs++;
    assoc->queue_usage[queue].cur_sched_nodes += sched_charge.nodes;
    assoc->queue_usage[queue].cur_sched_cores += sched_charge.cores;

    return true;
}


bool Job::release_sched_jobs ()
{
    if (!sched_charge.jobs)
        return false;

    sched_charge.assoc->cur_sched_jobs--;
    sched_charge.assoc->queue_usage[sched_charge.queue].cur_sched_jobs--;
    sched_charge.jobs = false;
    if (!sched_charge.resources)
        sched_charge = SchedCharge ();

    return true;
}


bool Job::release_sched_resources ()
{
    if (!sched_charge.resources)
        return false;

    sched_charge.assoc->queue_usage[sched_charge.queue].cur_sched_nodes -=
        sched_charge.nodes;
    sched_charge.assoc->queue_usage[sched_charge.queue].cur_sched_cores -=
        sched_charge.cores;
    sched_charge.resources = false;
    if (!sched_charge.jobs)
        sched_charge = SchedCharge ();

    return true;
}


bool Job::move_sched (Association *assoc, const std::string &queue)
{
    bool sched_jobs_charged = sched_charge.jobs;
    bool sched_resources_charged = sched_charge.resources;
    bool sched_usage_freed = false;
    int nodes = sched_charge.nodes;
    int cores = sched_charge.cores;

    if (sched_charge.assoc == assoc && sched_charge.queue == queue) {
        this->queue = queue;
        return false;
    }
    if (!sched_jobs_charged && !sched_resources_charged) {
        this->queue = queue;
        return false;
    }

    if (sched_jobs_charged)
        sched_usage_freed = release_sched_jobs ();
    if (sched_resources_charged)
        sched_usage_freed = release_sched_resources () || sched_usage_freed;

    this->queue = queue;

    sched_charge.assoc = assoc;
    sched_charge.queue = queue;
    sched_charge.nodes = nodes;
    sched_charge.cores = cores;
    sched_charge.jobs = sched_jobs_charged;
    sched_charge.resources = sched_resources_charged;

    if (sched_jobs_charged) {
        assoc->cur_sched_jobs++;
        assoc->queue_usage[queue].cur_sched_jobs++;
    }
    if (sched_resources_charged) {
        assoc->queue_usage[queue].cur_sched_nodes += sched_charge.nodes;
        assoc->queue_usage[queue].cur_sched_cores += sched_charge.cores;
    }

    return sched_usage_freed;
}
