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
#include <algorithm>
#include <unordered_map>
#include <cmath>

#include "job.hpp"

// - UNKNOWN_QUEUE: a queue is specified for a submitted job that flux-accounting
// does not know about
// - NO_QUEUE_SPECIFIED: no queue was specified for this job
// - INVALID_QUEUE: the association does not have permission to run jobs under
// this queue
#define UNKNOWN_QUEUE 0
#define NO_QUEUE_SPECIFIED 0
#define INVALID_QUEUE -6

// - UNKNOWN_PROJECT: a project that flux-accounting doesn't know about
// - INVALID_PROJECT: a project that the association doesn't have permission
// to charge jobs under
#define UNKNOWN_PROJECT -6
#define INVALID_PROJECT -7

// dependency names for flux-accounting dependencies
#define D_QUEUE_MRJ  "max-run-jobs-queue"
#define D_ASSOC_MRJ  "max-running-jobs-user-limit"
#define D_ASSOC_MRES "max-resources-user-limit"

// min_nodes_per_job, max_nodes_per_job, and max_time_per_job are not
// currently used or enforced in this plugin, so their values have no
// effect in queue limit enforcement.
class Queue {
public:
    std::string name = "";
    int min_nodes_per_job = 0;
    int max_nodes_per_job = std::numeric_limits<int>::max ();
    int max_time_per_job = std::numeric_limits<int>::max ();
    int priority = 0;
    int max_running_jobs = std::numeric_limits<int>::max ();
    int max_nodes_per_assoc = 2147483647;
};

// a class to track an association's usage in a particular queue
class QueueUsage {
public:
    int cur_run_jobs = 0; // number of running jobs in queue
    int cur_nodes = 0;    // number of nodes across all running jobs in queue
};

// all attributes are per-user/bank
class Association {
public:
    // attributes
    std::string bank_name;             // name of bank
    double fairshare;                  // fair share value
    int max_run_jobs;                  // max number of running jobs
    int cur_run_jobs;                  // current number of running jobs
    int max_active_jobs;               // max number of active jobs
    int cur_active_jobs;               // current number of active jobs
    std::vector<Job> held_jobs;        // vector to keep track of held Jobs
    std::vector<std::string> queues;   // list of accessible queues
    int queue_factor;                  // priority factor associated with queue
    double bank_factor;                // priority factor associated with bank
    int active;                        // active status
    std::vector<std::string> projects; // list of accessible projects
    std::string def_project;           // default project
    int max_nodes;                     // max num nodes across all running jobs
    int max_cores;                     // max num cores across all running jobs
    int cur_nodes;                     // current number of used nodes
    int cur_cores;                     // current number of used cores
    std::unordered_map<std::string, QueueUsage>
      queue_usage;                     // the association's usage per-queue

    // methods
    json_t* to_json () const;    // convert object to JSON string
    // check to see if a job can be released from all flux-accounting
    // dependencies
    bool under_max_run_jobs ();
    bool under_queue_max_run_jobs (const std::string &queue,
                                   std::map<std::string, Queue> queues);
    bool under_max_resources (const Job &job);
};

class Bank {
public:
    std::string name;        // name of the bank
    double priority = 0.0;   // priority associated with jobs under this bank
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

// validate a potentially passed-in queue by an association and return the
// integer priority associated with the queue
int get_queue_info (char *queue,
                    const std::vector<std::string> &permissible_queues,
                    const std::map<std::string, Queue> &queues);

// check the contents of the users map to see if every user's bank is a
// temporary "DNE" value; if it is, the plugin is still waiting on
// flux-accounting data
bool check_map_for_dne_only (std::map<int, std::map<std::string, Association>>
                               &users,
                             std::map<int, std::string> &users_def_bank);

// validate a potentially passed-in project by an association
int get_project_info (const char *project,
                      std::vector<std::string> &permissible_projects,
                      std::vector<std::string> projects);

// return the associated priority with a bank
double get_bank_priority (const char *bank,
                          const std::map<std::string, Bank> &banks);

#endif // ACCOUNTING_H
