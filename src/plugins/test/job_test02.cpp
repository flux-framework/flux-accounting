/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
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
    
#include "src/plugins/job.hpp"
#include "src/common/libtap/tap.h"


// Ensure that the creation of a Job object will initialize its members to
// default values.
void test_job_default_initialization ()
{
    Job job;

    ok (job.id == 0, "job ID is set to a default value of 0");
    ok (job.resources.empty (), "job resources map is empty by default");
    ok (job.nnodes () == 0, "job nnodes count is set to a default value of 0");
    ok (job.ncores () == 0, "job ncores count is set to a default value of 0");
    ok (job.deps.size () == 0, "job dependencies list is empty");
}


// Make sure that we can assign values to a Job object's members.
void test_job_member_assignment ()
{
    Job job;
    job.id = 1;
    job.resources["node"] = 16;
    job.resources["core"] = 8;
    job.add_dep ("dependency1");
    job.add_dep ("dependency2");

    ok (job.id == 1, "job ID can be set");
    ok (job.nnodes () == 16, "job nnodes can be defined");
    ok (job.ncores () == 8, "job ncores can be defined");
    ok (job.deps.size () == 2, "job dependencies list has 2 dependencies");
    ok (job.deps[0] == "dependency1", "first dependency is dependency1");
    ok (job.deps[1] == "dependency2", "second dependency is dependency2");
}


// Make sure get_resource () returns 0 for a resource type the job did not
// request instead of inserting a new key.
void test_job_get_resource_missing_type ()
{
    Job job;
    job.resources["node"] = 2;

    ok (job.get_resource ("gpu") == 0,
        "get_resource () returns 0 for a resource type not requested");
    ok (job.resources.size () == 1,
        "get_resource () does not insert missing keys into the map");
}


// Make sure count_resources () populates the job's resources map from a
// jobspec, including custom resource types.
void test_job_count_resources ()
{
    const char *spec = "{\"version\": 1, "
        "\"attributes\": {\"system\": {\"duration\": 3600.0}}, "
        "\"resources\": [{\"type\": \"node\", \"count\": 2, \"with\": "
        "[{\"type\": \"slot\", \"count\": 3, \"with\": "
        "[{\"type\": \"core\", \"count\": 4}, "
        "{\"type\": \"gpu\", \"count\": 1}, "
        "{\"type\": \"quantum\", \"count\": 2}]}]}]}";
    json_t *jobspec = json_loads (spec, 0, NULL);
    Job job;

    ok (job.count_resources (jobspec) == 0,
        "count_resources () succeeds on a valid jobspec");
    ok (job.nnodes () == 2, "count_resources () counts 2 total nodes");
    ok (job.ncores () == 24, "count_resources () counts 24 total cores");
    ok (job.get_resource ("gpu") == 6,
        "count_resources () counts 6 total gpus");
    ok (job.get_resource ("quantum") == 12,
        "count_resources () counts 12 total quantum devices");
    json_decref (jobspec);
}


// A jobspec that only requests cores still occupies at least one node, so
// count_resources () should report nnodes == 1.
void test_job_count_resources_cores_only ()
{
    const char *spec = "{\"version\": 1, "
        "\"attributes\": {\"system\": {\"duration\": 3600.0}}, "
        "\"resources\": [{\"type\": \"slot\", \"count\": 4, \"with\": "
        "[{\"type\": \"core\", \"count\": 2}]}]}";
    json_t *jobspec = json_loads (spec, 0, NULL);
    Job job;

    ok (job.count_resources (jobspec) == 0,
        "count_resources () succeeds on a cores-only jobspec");
    ok (job.nnodes () == 1,
        "a cores-only jobspec still occupies one node");
    ok (job.ncores () == 8, "count_resources () counts 8 total cores");
    json_decref (jobspec);
}


// Make sure count_resources () fails on an invalid jobspec.
void test_job_count_resources_failure ()
{
    const char *spec = "{\"version\": 1, "
        "\"attributes\": {\"system\": {\"duration\": 3600.0}}, "
        "\"resources\": [{\"type\": \"node\", \"count\": 1}]}";
    json_t *jobspec = json_loads (spec, 0, NULL);
    Job job;

    ok (job.count_resources (jobspec) == -1,
        "count_resources () fails on a jobspec with no slot");
    json_decref (jobspec);
}


// Make sure contains_dep () returns true when a Job contains a certain
// dependency.
void test_job_contains_dep_success ()
{
    Job job;
    job.id = 2;
    job.add_dep ("dependency1");
    
    ok (job.contains_dep ("dependency1") == true,
        "contains_dep () returns true on success");
}


// Make sure contains_dep () returns false when a Job does not contain a
// certain dependency.
void test_job_contains_dep_failure ()
{
    Job job;
    job.id = 3;
    
    ok (job.contains_dep ("foo") == false,
        "contains_dep () returns false on failure");
}


// Make sure we can remove dependencies from a Job object using remove_dep ().
void test_job_remove_dep_success ()
{
    Job job;
    job.id = 4;
    job.add_dep ("dependency1");
    job.add_dep ("dependency2");
    job.add_dep ("dependency3");
    
    ok (job.deps.size () == 3, "job dependencies list has 3 dependencies");
    job.remove_dep ("dependency1");
    ok (job.deps.size () == 2, "job dependencies get successfully removed");
    ok (job.deps[0] == "dependency2", "dependency2 moves to first slot");
    ok (job.deps[1] == "dependency3", "dependency3 moves to second slot");
}


// Make sure that a Job object's dependency list stays in tact even when
// trying to remove a dependency that does not exist.
void test_job_remove_dep_failure ()
{
    Job job;
    job.id = 5;
    job.add_dep ("dependency1");
    
    ok (job.deps.size () == 1, "job dependencies list has 1 dependency");
    job.remove_dep ("foo");
    ok (job.deps.size () == 1,
        "job dependencies list in tact after trying to remove nonexistent dependency");
}


int main (int argc, char* argv[])
{
    test_job_default_initialization ();
    test_job_member_assignment ();
    test_job_get_resource_missing_type ();
    test_job_count_resources ();
    test_job_count_resources_cores_only ();
    test_job_count_resources_failure ();
    test_job_contains_dep_success ();
    test_job_contains_dep_failure ();
    test_job_remove_dep_success ();
    test_job_remove_dep_failure ();

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
