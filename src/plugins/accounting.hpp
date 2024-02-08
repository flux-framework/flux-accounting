/************************************************************\
 * Copyright 2024 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

// header file for the Accounting class
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#ifndef ACCOUNTING_H
#define ACCOUNTING_H

#include <vector>
#include <string>
#include <map>
#include <iterator>
#include <sstream>

// all attributes are per-user/bank
class Association {
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
    json_t* to_json () const;    // convert object to JSON string
};

// get an Association object that points to user/bank in the users map;
// return nullptr on failure
Association* get_association (int userid,
                              const char *bank,
                              std::map<int, std::map<std::string, Association>>
                                &users,
                              std::map<int, std::string> &users_def_bank);

// iterate through the users map and construct a JSON object of each user/bank
json_t* convert_map_to_json (std::map<int, std::map<std::string, Association>>
                                 &users);

// split a list of items and add them to a vector in an Association object
void split_string_and_push_back (const char *list,
                                 std::vector<std::string> &vec);

#endif // ACCOUNTING_H
