/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

// header file for priority estimate callback helpers
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
}

#ifndef PRIORITIES_HPP
#define PRIORITIES_HPP

#include <map>
#include <string>

#include "accounting.hpp"

// A bundle of pointers to the state of the plugin; all of the associations,
// their default banks, all of the queues and banks, etc. This is used so that
// the estimator does not have to copy or maintain its own snapshot of the
// plugin state in order to give as real-time a view as possible. default_queue
// is empty when Flux has no configured default queue.
struct priority_estimate_ctx_t {
    std::map<int, std::map<std::string, Association>> *users;
    std::map<int, std::string> *users_def_bank;
    std::map<std::string, Queue> *queues;
    std::map<std::string, Bank> *banks;
    std::map<std::string, int> *priority_weights;
    bool *deny_unknown_queues;
    std::string *default_queue;
};

void estimate (flux_t *h,
               flux_msg_handler_t *mh,
               const flux_msg_t *msg,
               void *arg);

#endif // PRIORITIES_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
