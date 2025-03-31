/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include "job.hpp"

int count_resources (Job &job, json_t *jobspec)
{
    struct jj_counts counts;
    if (jj_get_counts_json (jobspec, &counts) < 0)
        return -1;
        
    job.nnodes = counts.nnodes;
    job.ncores = counts.nslots * counts.slot_size;
    return 0;
}


bool contains_dep (const Job &job, const std::string &dep)
{
    const auto &job_deps = job.deps;
    return std::find (job_deps.begin (),
                      job_deps.end (),
                      dep) != job_deps.end ();
}


void remove_dep (Job &job, const std::string &dep)
{
    auto &job_deps = job.deps;
    job_deps.erase (
        std::remove(job_deps.begin (), job_deps.end (), dep),
        job_deps.end ()
    );
}

