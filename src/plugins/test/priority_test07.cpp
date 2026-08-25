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
#include "src/common/libtap/tap.h"

// accounting.cpp references this global
bool deny_unknown_queues = false;

// default priority factor weights, mirroring the plugin's defaults
static std::map<std::string, int> weights = {
    {"fairshare", 100000},
    {"queue", 10000},
    {"bank", 0},
    {"urgency", 1000},
};

/*
 * A held job whose urgency is HOLD gets the minimum priority, short-circuiting
 * the weighted-sum calculation.
 */
static void hold_urgency_returns_min ()
{
    int64_t prio = calc_priority (0.5, 0, 0.0, FLUX_JOB_URGENCY_HOLD, weights);
    ok (prio == FLUX_JOB_PRIORITY_MIN,
        "HOLD urgency returns FLUX_JOB_PRIORITY_MIN");
}

/*
 * A held job whose urgency is EXPEDITE gets the maximum priority; this is how
 * an admin expedites a held job past earlier-submitted ones.
 */
static void expedite_urgency_returns_max ()
{
    int64_t prio =
        calc_priority (0.5, 0, 0.0, FLUX_JOB_URGENCY_EXPEDITE, weights);
    ok (prio == FLUX_JOB_PRIORITY_MAX,
        "EXPEDITE urgency returns FLUX_JOB_PRIORITY_MAX");
}

/*
 * A normal-urgency job's priority is the weighted sum of its factors. Two jobs
 * with the same factors but a higher queue factor sort higher.
 */
static void weighted_sum_orders_by_factors ()
{
    // fairshare only: 100000 * 0.5 == 50000
    int64_t base = calc_priority (0.5, 0, 0.0, FLUX_JOB_URGENCY_DEFAULT,
                                  weights);
    ok (base == 50000,
        "default-urgency priority is the weighted sum of its factors");

    // a higher queue factor increases priority: + 10000 * 5 == 100000
    int64_t higher_queue =
        calc_priority (0.5, 5, 0.0, FLUX_JOB_URGENCY_DEFAULT, weights);
    ok (higher_queue == 100000,
        "a higher queue factor yields a higher priority");
    ok (higher_queue > base,
        "job in a higher-priority queue sorts ahead of one in a lower queue");

    // urgency above default raises priority: + 1000 * (20 - 16) == 4000
    int64_t higher_urgency =
        calc_priority (0.5, 0, 0.0, 20, weights);
    ok (higher_urgency == 54000,
        "urgency above default raises priority");
    ok (higher_urgency > base,
        "job with higher urgency sorts ahead of a default-urgency job");
}

/*
 * A weighted sum that comes out negative clamps to the minimum priority rather
 * than returning a negative value.
 */
static void negative_sum_clamps_to_min ()
{
    // a negative queue weight with a positive queue factor drives the sum
    // negative: 0 + (-10000) * 5 == -50000
    std::map<std::string, int> neg_weights = {
        {"fairshare", 0},
        {"queue", -10000},
        {"bank", 0},
        {"urgency", 0},
    };
    int64_t prio =
        calc_priority (0.0, 5, 0.0, FLUX_JOB_URGENCY_DEFAULT, neg_weights);
    ok (prio == FLUX_JOB_PRIORITY_MIN,
        "a negative weighted sum clamps to FLUX_JOB_PRIORITY_MIN");
}

int main (int argc, char *argv[])
{
    hold_urgency_returns_min ();
    expedite_urgency_returns_max ();
    weighted_sum_orders_by_factors ();
    negative_sum_clamps_to_min ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
