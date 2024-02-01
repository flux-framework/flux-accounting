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

#ifndef ACCOUNTING_H
#define ACCOUNTING_H

#include <vector>
#include <string>
#include <map>
#include <iterator>

// all attributes are per-user/bank
class Association {
public:
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
};

#endif // ACCOUNTING_H
