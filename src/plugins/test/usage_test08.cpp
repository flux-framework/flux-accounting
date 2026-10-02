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

#include <cstdlib>

#include "src/plugins/jj.hpp"
#include "src/plugins/job.hpp"
#include "src/plugins/usage.hpp"
#include "src/common/libtap/tap.h"


static void test_usage_default_initialization ()
{
    Usage usage;

    ok (usage.jobs == 0, "usage jobs default to 0");
    ok (usage.resources.empty (), "usage resources default to empty");
}


static void test_usage_get_missing_type ()
{
    Usage usage;

    usage.resources["node"] = 2;

    ok (usage.get ("gpu") == 0,
        "get () returns 0 for a missing resource type");
    ok (usage.resources.size () == 1,
        "get () does not insert missing keys into the map");
}


static void test_usage_of_job ()
{
    Job job;
    Usage usage;

    job.resources["node"] = 2;
    job.resources["core"] = 64;
    job.resources["quantum"] = 4;

    usage = Usage::of (job);

    ok (usage.jobs == 1, "Usage::of (Job) counts one job");
    ok (usage.get ("node") == 2, "Usage::of (Job) copies node count");
    ok (usage.get ("core") == 64, "Usage::of (Job) copies core count");
    ok (usage.get ("quantum") == 4,
        "Usage::of (Job) copies arbitrary resource keys");
}


static void test_usage_of_jj_counts ()
{
    jj_counts counts;
    Usage usage;

    counts.counts["node"] = 1;
    counts.counts["core"] = 16;
    counts.counts["gpu"] = 2;

    usage = Usage::of (counts);

    ok (usage.jobs == 1, "Usage::of (jj_counts) counts one job");
    ok (usage.get ("node") == 1,
        "Usage::of (jj_counts) copies node count");
    ok (usage.get ("core") == 16,
        "Usage::of (jj_counts) copies core count");
    ok (usage.get ("gpu") == 2,
        "Usage::of (jj_counts) copies arbitrary resource keys");
}


static void test_usage_addition_assignment ()
{
    Usage u1;
    Usage u2;

    u1.jobs = 1;
    u1.resources["node"] = 2;
    u1.resources["core"] = 32;

    u2.jobs = 2;
    u2.resources["node"] = 3;
    u2.resources["gpu"] = 4;

    u1 += u2;

    ok (u1.jobs == 3, "operator+= adds job counts");
    ok (u1.get ("node") == 5, "operator+= accumulates shared keys");
    ok (u1.get ("core") == 32, "operator+= preserves left-only keys");
    ok (u1.get ("gpu") == 4, "operator+= adds right-only keys");
}


static void test_usage_subtraction_assignment ()
{
    Usage u1;
    Usage u2;

    u1.jobs = 3;
    u1.resources["node"] = 5;
    u1.resources["core"] = 32;
    u1.resources["gpu"] = 4;

    u2.jobs = 2;
    u2.resources["node"] = 3;
    u2.resources["core"] = 32;
    u2.resources["quantum"] = 6;

    u1 -= u2;

    ok (u1.jobs == 1, "operator-= subtracts job counts");
    ok (u1.get ("node") == 2, "operator-= subtracts shared keys");
    ok (u1.get ("core") == 0,
        "operator-= does not automatically prune zero values");
    ok (u1.resources.find ("core") != u1.resources.end (),
        "zero values remain present until prune ()");
    ok (u1.get ("gpu") == 4, "operator-= preserves left-only keys");
    ok (u1.get ("quantum") == -6,
        "operator-= records negative values before pruning");
}


static void test_usage_plus_operator ()
{
    Usage u1;
    Usage u2;
    Usage result;

    u1.jobs = 1;
    u1.resources["node"] = 2;

    u2.jobs = 1;
    u2.resources["node"] = 3;
    u2.resources["core"] = 8;

    result = u1 + u2;

    ok (result.jobs == 2, "operator+ returns combined job count");
    ok (result.get ("node") == 5, "operator+ accumulates shared keys");
    ok (result.get ("core") == 8, "operator+ adds distinct keys");
    ok (u1.jobs == 1 && u1.get ("node") == 2,
        "operator+ leaves left operand unchanged");
    ok (u2.jobs == 1 && u2.get ("node") == 3 && u2.get ("core") == 8,
        "operator+ leaves right operand unchanged");
}


static void test_usage_prune ()
{
    Usage u1;

    u1.jobs = -1;
    u1.resources["node"] = 2;
    u1.resources["core"] = 0;
    u1.resources["gpu"] = -1;

    u1.prune ();

    ok (u1.jobs == -1, "prune () leaves jobs unchanged");
    ok (u1.get ("node") == 2, "prune () preserves positive entries");
    ok (u1.resources.find ("core") == u1.resources.end (),
        "prune () removes zero entries");
    ok (u1.resources.find ("gpu") == u1.resources.end (),
        "prune () removes negative entries");
}


int main (int argc, char *argv[])
{
    test_usage_default_initialization ();
    test_usage_get_missing_type ();
    test_usage_of_job ();
    test_usage_of_jj_counts ();
    test_usage_addition_assignment ();
    test_usage_subtraction_assignment ();
    test_usage_plus_operator ();
    test_usage_prune ();

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
