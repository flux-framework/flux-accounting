/************************************************************\
 * Copyright 2014 Lawrence Livermore National Security, LLC
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

#include <errno.h>
#include <string.h>
#include <jansson.h>
}

#include "jj.hpp"

static int jj_read_level (json_t *o,
                          int level,
                          jj_counts &jj,
                          int multiplier);

/*  Count the resources requested by a single entry in the jobspec
 *  resources tree and add them to jj.counts.
 *
 *  A count in a jobspec is relative to its parent. If a job asks for
 *  2 nodes with 3 slots of 4 cores each, the 4 cores are per slot and
 *  the 3 slots are per node. To turn a relative count into a cluster
 *  wide total we multiply it by the total number of parent instances,
 *  which is passed in as multiplier and starts at 1 for the top level.
 *  That same total then becomes the multiplier for the children of this
 *  entry, so the example works out to 2 nodes, 6 slots, and 24 cores.
 */
static int jj_read_vertex (json_t *o,
                           int level,
                           jj_counts &jj,
                           int multiplier)
{
    int count;
    const char *type = NULL;
    json_t *with = NULL;
    json_error_t error;
    int exclusive = 0;

    // unpack the type and count for this entry along with the optional
    // exclusive flag and list of child resources
    if (json_unpack_ex (o, &error, 0, "{ s:s s:i s?b s?o }",
                       "type", &type,
                       "count", &count,
                       "exclusive", &exclusive,
                       "with", &with) < 0) {
        jj.error = "level " + std::to_string (level) + ": " + error.text;
        errno = EINVAL;
        return -1;
    }
    if (count <= 0) {
        jj.error = "Invalid count " + std::to_string (count)
                   + " for type '" + type + "'";
        errno = EINVAL;
        return -1;
    }
    // convert the relative count to a total. A type that appears more
    // than once in the tree adds up rather than being overwritten
    int total = multiplier * count;
    jj.counts[type] += total;
    // an exclusive allocation can only be requested on a node
    if (strcmp (type, "node") == 0 && exclusive)
        jj.exclusive = true;
    // count this entry's child resources, with this entry's total as
    // the children's multiplier
    if (with)
        return jj_read_level (with, level + 1, jj, total);
    return 0;
}

static int jj_read_level (json_t *o,
                          int level,
                          jj_counts &jj,
                          int multiplier)
{
    size_t i;
    json_t *v = NULL;

    if (!json_is_array (o)) {
        jj.error = "level " + std::to_string (level) + ": must be an array";
        errno = EINVAL;
        return -1;
    }
    json_array_foreach (o, i, v) {
        if (jj_read_vertex (v, level, jj, multiplier) < 0)
            return -1;
    }
    return 0;
}

int jj_get_counts (const char *spec, jj_counts &jj)
{
    json_t *o = NULL;
    json_error_t error;
    int rc = -1;

    if ((o = json_loads (spec, 0, &error)) == NULL) {
        jj = jj_counts ();
        jj.error = std::string ("JSON load: ") + error.text;
        errno = EINVAL;
        return -1;
    }

    rc = jj_get_counts_json (o, jj);
    json_decref (o);
    return rc;
}

int jj_get_counts_json (json_t *jobspec, jj_counts &jj)
{
    int version;
    json_t *resources = NULL;
    json_error_t error;

    jj = jj_counts ();

    if (json_unpack_ex (jobspec, &error, 0, "{s:i s:o}",
                        "version", &version,
                        "resources", &resources) < 0) {
        jj.error = std::string ("at top level: ") + error.text;
        errno = EINVAL;
        return -1;
    }
    /* jobspec version check omitted as discussed in #6632 and #6682
     * N.B. attributes.system is generally optional, but
     * attributes.system.duration is required in jobspec version 1 */
    if (json_unpack_ex (jobspec, &error, 0, "{s:{s:{s:F}}}",
                        "attributes",
                          "system",
                            "duration", &jj.duration) < 0) {
        jj.error = std::string ("at top level: getting duration: ")
                   + error.text;
        errno = EINVAL;
        return -1;
    }
    if (jj_read_level (resources, 0, jj, 1) < 0)
        return -1;

    if (jj.get ("slot") <= 0) {
        jj.error = "Unable to determine slot count";
        errno = EINVAL;
        return -1;
    }
    if (jj.get ("core") <= 0) {
        jj.error = "Unable to determine slot size";
        errno = EINVAL;
        return -1;
    }
    /* a jobspec that requests cores without nodes still occupies at least
     * one node, so the node, slot, and core keys are always present with
     * counts of at least 1 after a successful parse */
    if (jj.get ("node") == 0)
        jj.counts["node"] = 1;
    return 0;
}

/* vi: ts=4 sw=4 expandtab
 */
