/************************************************************\
 * Copyright 2023 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

// header file for the bank_info class
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#ifndef BANK_INFO_H
#define BANK_INFO_H

#include <vector>
#include <string>
#include <map>
#include <iterator>

// all attributes are per-user/bank
class user_bank_info {
public:
    // attributes
    std::string bank_name;           // name of bank
    double fairshare;                // fair share value
    int max_run_jobs;                // max number of running jobs
    int cur_run_jobs;                // current number of running jobs 
    int max_active_jobs;             // max number of active jobs
    int cur_active_jobs;             // current number of active jobs
    std::vector<long int> held_jobs; // list of currently held job ID's
    std::vector<std::string> queues; // list of accessible queues
    int queue_factor;                // priority factor associated with queue
    int active;                      // active status

    // methods
    std::string to_json () const;    // convert object to JSON string
};

// these data structures are defined in the priority plugin
extern std::map<int, std::map<std::string, user_bank_info>> users;
extern std::map<int, std::string> users_def_bank;

// get a user_bank_info object that points to user/bank
// information in users map; return NULL on failure
user_bank_info* get_user_info (int userid, char *bank);

// iterate through the users map and construct a JSON object of each user/bank
json_t* map_to_json ();

#endif // BANK_INFO_H
