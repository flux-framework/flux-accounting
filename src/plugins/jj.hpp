/************************************************************\
 * Copyright 2014 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* jj.hpp - read a JSON jobspec and count the resources it requests
 *
 * The name jj is short for JSON jobspec. This code was originally
 * derived from jj.c in flux-core, which itself began as a simple json
 * jobspec reader in the sched-simple scheduler module. The version here
 * is generalized for flux-accounting. Instead of tracking a fixed set
 * of resource types (node, slot, core, gpu) in dedicated struct members,
 * it records every resource type found in the jobspec in a map from
 * type name to total count, so custom resource types are counted too.
 */

#ifndef HAVE_JJ_H
#define HAVE_JJ_H 1

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif

#include <jansson.h>
}

#include <map>
#include <string>

/* Look up a type in a resource count map, returning 0 if it is absent.
 * Never inserts a key. */
inline int resource_count (const std::map<std::string, int> &counts,
                           const std::string &type)
{
    auto it = counts.find (type);
    return it == counts.end () ? 0 : it->second;
}

struct jj_counts {
    /* the total amount of each resource type requested by the jobspec,
     * keyed by type name such as node, core, or gpu. Totals include
     * multipliers from parent resources, so 2 nodes with 3 slots of 4
     * cores each counts as 24 cores. After a successful parse the node,
     * slot, and core keys are guaranteed to be present with counts of
     * at least 1. Use get () for a safe lookup of any other type. */
    std::map<std::string, int> counts;

    bool exclusive = false; /* node-exclusive allocation requested */

    double duration = 0.0;  /* attributes.system.duration if set */

    std::string error;      /* on error, contains error description */

    /* Look up the total count for a resource type. Returns 0 if the
     * type was not present in the jobspec. */
    int get (const std::string &type) const
    {
        return resource_count (counts, type);
    }
};

/*  Parse jobspec from the json string spec and return a resource request
 *   summary in counts on success.
 *  Returns 0 on success and -1 on failure with errno set and counts.error
 *   set to an error message string.
 */
int jj_get_counts (const char *spec, jj_counts &counts);

/*  Identical to jj_get_counts, but take json_t  */
int jj_get_counts_json (json_t *jobspec, jj_counts &counts);

#endif /* !HAVE_JJ_H */
