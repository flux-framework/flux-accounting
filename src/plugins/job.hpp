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

class Job {
public:
    // attributes
    flux_jobid_t id = 0;               // the ID of the job
    std::vector<std::string> deps; // any dependencies on job
    int nnodes = 0;                // the number of nodes requested
    int ncores = 0;                // the number of cores requested
    std::string queue;             // the queue the job was submitted under

    // constructor
    Job () = default;

    // methods
    // count the resources requested for a job
    int count_resources (json_t *jobspec);

    // add a dependency to the job's list of dependencies
    void add_dep (const std::string &dep);

    // determine if a job contains a certain dependency
    bool contains_dep (const std::string &dep) const;

    // remove a job dependency from a job's list of dependencies
    void remove_dep (const std::string &dep);
};

#endif // JOB_H
