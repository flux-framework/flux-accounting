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
#include <errno.h>
}

#include "src/plugins/jj.hpp"
#include "src/common/libtap/tap.h"

// helper to wrap a resources JSON fragment in a minimal valid jobspec
static std::string make_jobspec (const std::string &resources,
                                 const std::string &duration = "3600.0")
{
    return "{\"version\": 1, "
           "\"attributes\": {\"system\": {\"duration\": " + duration + "}}, "
           "\"resources\": " + resources + "}";
}


// A standard node->slot->core/gpu jobspec is counted as totals for every
// resource type, matching the semantics of the original fixed-field parser.
void test_basic_counts ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"node\", \"count\": 2, \"with\": "
        "[{\"type\": \"slot\", \"count\": 3, \"with\": "
        "[{\"type\": \"core\", \"count\": 4}, "
        "{\"type\": \"gpu\", \"count\": 1}]}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds on a valid jobspec");
    ok (counts.get ("node") == 2, "2 total nodes are counted");
    ok (counts.get ("slot") == 6, "6 total slots are counted");
    ok (counts.get ("core") == 24, "24 total cores are counted");
    ok (counts.get ("gpu") == 6, "6 total gpus are counted");
    ok (counts.exclusive == false, "exclusive defaults to false");
    ok (counts.duration == 3600.0, "duration is parsed");
    ok (counts.error.empty (), "no error is set on success");
}


// A jobspec that only requests slots/cores still occupies at least one
// node, so "node" is guaranteed to be present with a count >= 1.
void test_cores_only_normalizes_node ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"slot\", \"count\": 4, \"with\": "
        "[{\"type\": \"core\", \"count\": 2}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds on a cores-only jobspec");
    ok (counts.get ("node") == 1,
        "a cores-only jobspec is normalized to one node");
    ok (counts.get ("slot") == 4, "4 total slots are counted");
    ok (counts.get ("core") == 8, "8 total cores are counted");
}


// Custom resource types are counted just like the standard types, with
// parent multipliers applied.
void test_custom_resource_types ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"node\", \"count\": 2, \"with\": "
        "[{\"type\": \"slot\", \"count\": 3, \"with\": "
        "[{\"type\": \"core\", \"count\": 4}, "
        "{\"type\": \"quantum\", \"count\": 2}]}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds on a jobspec with a custom type");
    ok (counts.get ("quantum") == 12,
        "12 total quantum devices are counted (2 nodes x 3 slots x 2)");
}


// Multiple resource entries of the same type are accumulated. The original
// fixed-field parser overwrote on repeat, undercounting jobspecs with
// multiple slot entries at the same level.
void test_multiple_entries_accumulate ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"slot\", \"count\": 2, \"with\": "
        "[{\"type\": \"core\", \"count\": 4}]}, "
        "{\"type\": \"slot\", \"count\": 3, \"with\": "
        "[{\"type\": \"core\", \"count\": 2}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds on a jobspec with two slot entries");
    ok (counts.get ("slot") == 5, "slot counts accumulate (2 + 3 == 5)");
    ok (counts.get ("core") == 14,
        "core counts accumulate per branch (2x4 + 3x2 == 14)");
}


// The exclusive flag is honored when set on a node vertex.
void test_exclusive ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"node\", \"count\": 1, \"exclusive\": true, \"with\": "
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}]}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds on an exclusive jobspec");
    ok (counts.exclusive == true, "exclusive is set from the node vertex");
}


// get () returns 0 for missing resource types and never inserts new keys.
void test_get_missing_type ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"node\", \"count\": 1, \"with\": "
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}]}]}]");

    ok (jj_get_counts (spec.c_str (), counts) == 0,
        "jj_get_counts () succeeds");
    ok (counts.get ("gpu") == 0,
        "get () returns 0 for a resource type not in the jobspec");
    ok (counts.counts.size () == 3,
        "get () does not insert missing keys into the map");
}


// A jj_counts object is reset between calls so stale state from a previous
// parse cannot leak into a new one.
void test_counts_reset_between_calls ()
{
    jj_counts counts;
    std::string spec1 = make_jobspec (
        "[{\"type\": \"node\", \"count\": 4, \"exclusive\": true, \"with\": "
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}, "
        "{\"type\": \"gpu\", \"count\": 2}]}]}]");
    std::string spec2 = make_jobspec (
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}]}]", "60.0");

    ok (jj_get_counts (spec1.c_str (), counts) == 0,
        "first jj_get_counts () call succeeds");
    ok (jj_get_counts (spec2.c_str (), counts) == 0,
        "second jj_get_counts () call succeeds");
    ok (counts.get ("node") == 1, "node count is from the second jobspec");
    ok (counts.get ("gpu") == 0, "gpu count from the first jobspec is reset");
    ok (counts.exclusive == false, "exclusive flag is reset");
    ok (counts.duration == 60.0, "duration is from the second jobspec");
}


// A jobspec with no slot fails with a descriptive error.
void test_error_missing_slot ()
{
    jj_counts counts;
    std::string spec = make_jobspec ("[{\"type\": \"node\", \"count\": 1}]");

    errno = 0;
    ok (jj_get_counts (spec.c_str (), counts) == -1,
        "jj_get_counts () fails on a jobspec with no slot");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error == "Unable to determine slot count",
        "error message describes the missing slot");
}


// A jobspec with a slot but no cores fails with a descriptive error.
void test_error_missing_core ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"gpu\", \"count\": 1}]}]");

    errno = 0;
    ok (jj_get_counts (spec.c_str (), counts) == -1,
        "jj_get_counts () fails on a jobspec with no cores");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error == "Unable to determine slot size",
        "error message describes the missing cores");
}


// A resource vertex with an invalid count fails.
void test_error_invalid_count ()
{
    jj_counts counts;
    std::string spec = make_jobspec (
        "[{\"type\": \"slot\", \"count\": 0, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}]}]");

    errno = 0;
    ok (jj_get_counts (spec.c_str (), counts) == -1,
        "jj_get_counts () fails on a count of 0");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error == "Invalid count 0 for type 'slot'",
        "error message describes the invalid count");
}


// A resources section that is not an array fails.
void test_error_resources_not_array ()
{
    jj_counts counts;
    std::string spec = make_jobspec ("{\"type\": \"node\", \"count\": 1}");

    errno = 0;
    ok (jj_get_counts (spec.c_str (), counts) == -1,
        "jj_get_counts () fails when resources is not an array");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error == "level 0: must be an array",
        "error message describes the malformed level");
}


// A jobspec missing attributes.system.duration fails.
void test_error_missing_duration ()
{
    jj_counts counts;
    std::string spec = "{\"version\": 1, \"resources\": "
        "[{\"type\": \"slot\", \"count\": 1, \"with\": "
        "[{\"type\": \"core\", \"count\": 1}]}]}";

    errno = 0;
    ok (jj_get_counts (spec.c_str (), counts) == -1,
        "jj_get_counts () fails on a jobspec with no duration");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error.find ("getting duration") != std::string::npos,
        "error message mentions the duration");
}


// A jobspec missing version/resources at the top level fails.
void test_error_missing_top_level_keys ()
{
    jj_counts counts;

    errno = 0;
    ok (jj_get_counts ("{\"version\": 1}", counts) == -1,
        "jj_get_counts () fails on a jobspec with no resources");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error.find ("at top level") != std::string::npos,
        "error message mentions the top level");
}


// A string that is not valid JSON fails.
void test_error_invalid_json ()
{
    jj_counts counts;

    errno = 0;
    ok (jj_get_counts ("this is not json", counts) == -1,
        "jj_get_counts () fails on invalid JSON");
    ok (errno == EINVAL, "errno is set to EINVAL");
    ok (counts.error.find ("JSON load") != std::string::npos,
        "error message mentions the JSON load failure");
}


int main (int argc, char* argv[])
{
    test_basic_counts ();
    test_cores_only_normalizes_node ();
    test_custom_resource_types ();
    test_multiple_entries_accumulate ();
    test_exclusive ();
    test_get_missing_type ();
    test_counts_reset_between_calls ();
    test_error_missing_slot ();
    test_error_missing_core ();
    test_error_invalid_count ();
    test_error_resources_not_array ();
    test_error_missing_duration ();
    test_error_missing_top_level_keys ();
    test_error_invalid_json ();

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
