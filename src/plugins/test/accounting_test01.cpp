/************************************************************\
 * Copyright 2024 Lawrence Livermore National Security, LLC
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

#include <iostream>
#include <fstream>
#include <vector>
#include <map>
#include <string>

#include "src/plugins/accounting.hpp"
#include "src/common/libtap/tap.h"

// define a test users map to run tests on
std::map<int, std::map<std::string, Association>> users;
std::map<int, std::string> users_def_bank;


/*
 * helper function to add a user/bank to the users map
 */
void add_user_to_map (
                std::map<int, std::map<std::string, Association>> &users,
                int userid,
                const std::string& bank,
                Association a)
{
    // insert user to users map
    users[userid][bank] = {
        a.bank_name,
        a.fairshare,
        a.max_run_jobs,
        a.cur_run_jobs,
        a.max_active_jobs,
        a.cur_active_jobs,
        a.held_jobs,
        a.queues,
        a.queue_factor,
        a.active
    };
}


/*
 * helper function to add test users to the users map
 */
void initialize_map (
    std::map<int, std::map<std::string, Association>> &users)
{
    Association user1 = {"bank_A", 0.5, 5, 0, 7, 0, {}, {}, 0, 1};
    Association user2 = {"bank_A", 0.5, 5, 0, 7, 0, {}, {}, 0, 1};

    add_user_to_map (users, 1001, "bank_A", user1);
    users_def_bank[1001] = "bank_A";

    // purposely do not add user2 to the def_bank_map
    add_user_to_map (users, 1002, "bank_A", user2);
}


// ensure we can access a user/bank in the users map
static void test_direct_map_access (
    std::map<int, std::map<std::string, Association>> &users)
{
    ok (users[1001]["bank_A"].bank_name == "bank_A", 
        "a user/bank from users map can be accessed directly");
}


int main (int argc, char* argv[])
{
    // declare the number of tests that we plan to run
    plan (1);

    // add users to the test map
    initialize_map (users);

    test_direct_map_access (users);

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
