/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

// header file for the Accounting class
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

// all attributes are per-user/bank
class Job {
public:
    // attributes
    long int id = 0;               // the ID of the job
    std::vector<std::string> deps; // any dependencies on job
    int nnodes = 0;                // the number of nodes requested
    int ncores = 0;                // the number of cores requested

    // constructor
    Job () = default;
    Job (long int id_) : id (id_), nnodes (0), ncores (0) {}
};

// count the resources requested for a job
int count_resources (Job &job, json_t *jobspec);

// determine if a job contains a certain dependency
bool contains_dep (const Job &job, const std::string &dep);

// remove a job dependency from a job's list of dependencies
void remove_dep (Job &job, const std::string &dep);

#endif // JOB_H
