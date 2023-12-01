/************************************************************\
 * Copyright 2023 Lawrence Livermore National Security, LLC
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

#include "src/plugins/bank_info.hpp"
#include "src/common/libtap/tap.h"

// define a test users map to run tests on
std::map<int, std::map<std::string, user_bank_info>> users;
std::map<int, std::string> users_def_bank;


/*
 * helper function to add a user/bank to the users map
 */
void add_user_to_map (
                std::map<int, std::map<std::string, user_bank_info>> &users,
                int userid,
                const std::string& bank,
                user_bank_info user_bank)
{
    // insert user to users map
    users[userid][bank] = {
        user_bank.bank_name,
        user_bank.fairshare,
        user_bank.max_run_jobs,
        user_bank.cur_run_jobs,
        user_bank.max_active_jobs,
        user_bank.cur_active_jobs,
        user_bank.held_jobs,
        user_bank.queues,
        user_bank.queue_factor,
        user_bank.active
    };
}


/*
 * helper function to add a user/bank to the default bank map
 */
void add_user_to_def_bank_map (std::map<int, std::string> &users_def_bank,
                               int userid,
                               const std::string& bank)
{
    users_def_bank[userid] = bank;
}


/*
 * helper function to add test users to the users map
 */
void initialize_map (
    std::map<int, std::map<std::string, user_bank_info>> &users)
{
    user_bank_info user1 = {"bank_A", 0.5, 5, 0, 7, 0, {}, {}, 0, 1};
    user_bank_info user2 = {"bank_A", 0.5, 5, 0, 7, 0, {}, {}, 0, 1};

    add_user_to_map (users, 1001, "bank_A", user1);
    add_user_to_def_bank_map (users_def_bank, 1001, "bank_A");

    // purposely do not add user2 to the def_bank_map
    add_user_to_map (users, 1002, "bank_A", user2);
}


static void test_basic_string_comparison ()
{
    const std::string string1 = "hello, world!";
    const std::string string2 = "hello, world!";

    ok (string1 == string2, "i can perform a basic string comparison test");
}


// ensure we can access a user/bank in the users map
static void test_direct_map_access (
    std::map<int, std::map<std::string, user_bank_info>> &users)
{
    ok (users[1001]["bank_A"].bank_name == "bank_A", 
        "a user/bank from users map can be accessed directly");
}


// ensure the user_bank_info object is returned when a user/map
// exists in the map
static void test_get_user_info_success ()
{
    // retrieve user_bank_info object
    user_bank_info *user1 = get_user_info (1001,
                                           const_cast<char *> ("bank_A"));
    ok (user1->bank_name == "bank_A",
        "get_user_info () returns a pointer to a user_bank_info object "
        "on success");
}


// ensure NULL is returned when a user cannot be found in the map
static void test_get_user_info_user_noexist ()
{
    user_bank_info *user_foo = get_user_info (9999,
                                              const_cast<char *> ("bank_A"));
    ok (user_foo == NULL,
        "get_user_info () returns NULL when a user/bank cannot be found");
}


// ensure NULL is returned when a user does not have a default bank
static void test_get_user_info_user_no_default_bank ()
{
    user_bank_info *user2 = get_user_info (1002, NULL);
    ok (user2 == NULL,
        "get_user_info () returns NULL when a user does not have "
        "a default bank");
}


int main (int argc, char* argv[])
{
    // declare the number of tests that we plan to run
    plan (5);

    // add users to the test map
    initialize_map (users);

    test_basic_string_comparison ();
    test_direct_map_access (users);
    test_get_user_info_success ();
    test_get_user_info_user_noexist ();
    test_get_user_info_user_no_default_bank ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
