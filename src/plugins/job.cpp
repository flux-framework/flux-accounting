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
