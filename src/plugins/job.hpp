/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

// header file for the Job class
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#ifndef JOB_H
#define JOB_H

#include <vector>
#include <string>
#include <map>
#include <iterator>
#include <sstream>
#include <algorithm>

// custom job resource counting file
#include "jj.hpp"

class Association;

struct SchedCharge {
    Association *assoc = nullptr;
    std::string queue;
    int nodes = 0;
    int cores = 0;
    bool jobs = false;
    bool resources = false;
};

class Job {
public:
    // attributes
    flux_jobid_t id = 0;           // the ID of the job
    std::vector<std::string> deps; // any dependencies on job
    // the total amount of each resource type requested, keyed by type
    // name such as node or core. Populated by count_resources ()
    std::map<std::string, int> resources;
    std::string queue;             // the queue the job was submitted under
    double fairshare = -1.0;       // fair-share value associated with this job

    // constructor
    Job () = default;

    // methods
    // count the resources requested for a job
    int count_resources (json_t *jobspec);

    // look up the total count requested for a resource type. Returns 0
    // if the job did not request the type
    int get_resource (const std::string &type) const
    {
        return resource_count (resources, type);
    }

    // convenience accessors for the resource types currently tracked by
    // the plugin's limits
    int nnodes () const { return get_resource ("node"); }
    int ncores () const { return get_resource ("core"); }

    // charge or release this job's SCHED usage
    bool charge_sched (Association *assoc, const std::string &queue);
    bool release_sched_jobs ();
    bool release_sched_resources ();
    bool move_sched (Association *assoc, const std::string &queue);
    bool sched_jobs_charged () const { return sched_charge.jobs; }
    bool sched_resources_charged () const { return sched_charge.resources; }

    // add a dependency to the job's list of dependencies
    void add_dep (const std::string &dep);

    // determine if a job contains a certain dependency
    bool contains_dep (const std::string &dep) const;

    // remove a job dependency from a job's list of dependencies
    void remove_dep (const std::string &dep);

private:
    SchedCharge sched_charge;
};

#endif // JOB_H
