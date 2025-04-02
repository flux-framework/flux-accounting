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
    ok (job.nnodes == 0, "job nnodes count is set to a default value of 0");
    ok (job.ncores == 0, "job ncores count is set to a default value of 0");
    ok (job.deps.size () == 0, "job dependencies list is empty");
}


// Make sure that we can assign values to a Job object's members.
void test_job_member_assignment ()
{
    Job job;
    job.id = 1;
    job.nnodes = 16;
    job.ncores = 8;
    job.add_dep ("dependency1");
    job.add_dep ("dependency2");

    ok (job.id == 1, "job ID can be set");
    ok (job.nnodes == 16, "job nnodes can be defined");
    ok (job.ncores == 8, "job ncores can be defined");
    ok (job.deps.size () == 2, "job dependencies list has 2 dependencies");
    ok (job.deps[0] == "dependency1", "first dependency is dependency1");
    ok (job.deps[1] == "dependency2", "second dependency is dependency2");
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
