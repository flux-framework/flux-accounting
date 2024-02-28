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
// define a test queues map
std::map<std::string, Queue> queues;


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


/*
 * helper function to add test queues to the queues map
 */
void initialize_queues () {
    queues["bronze"] = {0, 5, 60, 100};
    queues["silver"] = {0, 5, 60, 200};
    queues["gold"] = {0, 5, 60, 300};
}


// ensure we can access a user/bank in the users map
static void test_direct_map_access (
    std::map<int, std::map<std::string, Association>> &users)
{
    ok (users[1001]["bank_A"].bank_name == "bank_A", 
        "a user/bank from users map can be accessed directly");
}


// ensure an Assocation* is returned on success
static void test_get_association_success ()
{
    // retrieve user_bank_info object
    Association *user1 = get_association (1001,
                                          const_cast<char *> ("bank_A"),
                                          users,
                                          users_def_bank);
    ok (user1->bank_name == "bank_A",
        "get_association () successfully returns a pointer to an Association");
}


// ensure nullptr is returned when a user cannot be found in the map
static void test_get_association_noexist ()
{
    Association *user_foo = get_association (9999,
                                             const_cast<char *> ("bank_A"),
                                             users,
                                             users_def_bank);
    ok (user_foo == nullptr,
        "get_association () fails when an association cannot be found");
}


// ensure nullptr is returned when a user does not have a default bank
static void test_get_association_no_default_bank ()
{
    Association *user2 = get_association (1002, NULL, users, users_def_bank);
    ok (user2 == nullptr,
        "get_association () fails when a user does not have a default bank");
}


// ensure split_string_and_push_back () works with a list of items
static void split_string_and_push_back_success ()
{
    const char *assoc_queues = "bronze,silver,gold";
    std::vector<std::string> expected_queues = {"bronze", "silver", "gold"};

    split_string_and_push_back (assoc_queues, users[1001]["bank_A"].queues);
    ok (users[1001]["bank_A"].queues == expected_queues,
        "split_string_and_push_back () works");
}


// ensure the correct priority factor is returned for a valid queue
static void test_get_queue_info_success ()
{
    Association a = users[1001]["bank_A"];
    a.queues = {"bronze", "silver"};
    a.queue_factor = get_queue_info (const_cast<char *> ("bronze"),
                                     a.queues,
                                     queues);

    ok (a.queue_factor == 100,
        "get_queue_info () returns the associated priority on success");
}


// ensure NO_QUEUE_SPECIFIED is returned when queue is NULL
static void test_get_queue_info_no_queue_specified ()
{
    Association a = users[1001]["bank_A"];
    a.queue_factor = get_queue_info (NULL, a.queues, queues);

    ok (a.queue_factor == NO_QUEUE_SPECIFIED,
        "NO_QUEUE_SPECIFIED is returned when no queue is passed in");
}


// ensure UNKOWN_QUEUE is returned when an unrecognized queue is passed in
static void test_get_queue_info_unknown_queue ()
{
    Association a = users[1001]["bank_A"];
    a.queue_factor = get_queue_info (const_cast<char *> ("platinum"),
                                     a.queues,
                                     queues);

    ok (a.queue_factor == UNKNOWN_QUEUE,
        "UNKNOWN_QUEUE is returned when an unrecognized queue is passed in");
}


// ensure INVALID_QUEUE is returned when an unrecognized queue is passed in
static void test_get_queue_info_invalid_queue ()
{
    Association a = users[1001]["bank_A"];
    a.queues = {"bronze", "silver"};
    a.queue_factor = get_queue_info (const_cast<char *> ("gold"),
                                     a.queues,
                                     queues);

    ok (a.queue_factor == INVALID_QUEUE,
        "INVALID_QUEUE is returned when an inaccessible queue is passed in");
}


int main (int argc, char* argv[])
{
    // declare the number of tests that we plan to run
    plan (9);

    // add users to the test map
    initialize_map (users);
    // add queues to the test queues map
    initialize_queues ();

    test_direct_map_access (users);
    test_get_association_success ();
    test_get_association_noexist ();
    test_get_association_no_default_bank ();
    split_string_and_push_back_success ();
    test_get_queue_info_success ();
    test_get_queue_info_no_queue_specified ();
    test_get_queue_info_unknown_queue ();
    test_get_queue_info_invalid_queue ();
    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
