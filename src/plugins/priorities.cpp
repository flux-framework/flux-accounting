/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* priorities.cpp - priority RPCs for mf_priority plugin
 *
 */
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#include <cerrno>
#include <cstdint>
#include <map>
#include <string>

#include "accounting.hpp"
#include "priorities.hpp"

// every row in the result has the same keys; a "queue=null" means the estimate
// used no queue factor, while ineligible rows display "priority=null"
static int add_estimate_result (json_t *results,
                                const std::string &bank,
                                const char *queue,
                                int urgency,
                                int64_t priority,
                                const char *errmsg)
{
    json_t *row = json_object ();

    if (!row)
        return -1;

    if (json_object_set_new (row, "bank", json_string (bank.c_str ())) < 0
        || json_object_set_new (row,
                                "queue",
                                queue ? json_string (queue) : json_null ()) < 0
        || json_object_set_new (row, "urgency", json_integer (urgency)) < 0)
        return -1;

    if (errmsg) {
        if (json_object_set_new (row, "priority", json_null ()) < 0
            || json_object_set_new (row, "error", json_string (errmsg)) < 0)
            return -1;
    } else {
        if (json_object_set_new (row, "priority", json_integer (priority)) < 0
            || json_object_set_new (row, "error", json_null ()) < 0)
            return -1;
    }

    if (json_array_append_new (results, row) < 0)
        // append_new () decref's even when returning < 0
        return -1;

    return 0;
}


static const char *validate_estimate_assoc (priority_estimate_ctx_t *ctx,
                                            Association *a,
                                            const char *queue)
{
    if (a->active == 0)
        return "user/bank entry has been disabled from flux-accounting DB";

    // reflect the current policy of denying unknown queues vs. allowing them
    if (*ctx->deny_unknown_queues && queue != NULL
        && ctx->queues->find (std::string (queue)) == ctx->queues->end ())
        return "queue is unknown to flux-accounting and "
               "deny-unknown-queues is enabled";

    if (!queue_permitted (queue, a->queues, *ctx->queues))
        return "queue not valid for user";

    return NULL;
}


static int append_priority_estimate (json_t *results,
                                     priority_estimate_ctx_t *ctx,
                                     Association *a,
                                     const char *queue,
                                     int urgency)
{
    const char *errmsg = validate_estimate_assoc (ctx, a, queue);
    int64_t priority = 0;

    if (!errmsg) {
        std::string queue_name = queue ? queue : "";
        int queue_factor = get_queue_priority (queue_name, *ctx->queues);
        double bank_factor = get_bank_priority (a->bank_name.c_str (),
                                                *ctx->banks);

        priority = calc_priority (a->fairshare,
                                  queue_factor,
                                  bank_factor,
                                  urgency,
                                  *ctx->priority_weights);
    }

    return add_estimate_result (results,
                                a->bank_name,
                                queue,
                                urgency,
                                priority,
                                errmsg);
}


// do a read-only association lookup
static Association *get_estimate_association (priority_estimate_ctx_t *ctx,
                                              int userid,
                                              const char *bank)
{
    auto user_it = ctx->users->find (userid);
    std::string bank_name;

    if (user_it == ctx->users->end ())
        return nullptr;

    if (bank != NULL) {
        bank_name = bank;
    } else {
        auto def_it = ctx->users_def_bank->find (userid);

        if (def_it == ctx->users_def_bank->end ())
            return nullptr;
        bank_name = def_it->second;
    }

    auto bank_it = user_it->second.find (bank_name);
    if (bank_it == user_it->second.end ())
        return nullptr;

    return &bank_it->second;
}


// Estimate the priority of a job given the plugin's current in-memory state;
// it will not change the state of the association, queue, or job.
void estimate (flux_t *h,
               flux_msg_handler_t *mh,
               const flux_msg_t *msg,
               void *arg)
{
    priority_estimate_ctx_t *ctx = static_cast<priority_estimate_ctx_t *> (arg);
    const char *bank = NULL;
    const char *queue = NULL;
    int all_banks = 0;
    int urgency = FLUX_JOB_URGENCY_DEFAULT;
    struct flux_msg_cred cred;
    json_t *results = NULL;
    const char *errmsg = NULL;

    // a malformed payload is an error; on failure, errno is set to EPROTO and
    // the message's last error describes the bad key
    if (flux_request_unpack (msg,
                             NULL,
                             "{s?s s?b s?s s?i}",
                             "bank", &bank,
                             "all_banks", &all_banks,
                             "queue", &queue,
                             "urgency", &urgency) < 0)
        goto error;

    // use authenticated message credentials; the request payload must not
    // choose which userid is being estimated
    if (flux_msg_get_cred (msg, &cred) < 0)
        goto error;

    if (bank && all_banks) {
        errno = EINVAL;
        errmsg = "bank and all_banks are mutually exclusive";
        goto error;
    }
    if (urgency < FLUX_JOB_URGENCY_HOLD
        || urgency > FLUX_JOB_URGENCY_EXPEDITE) {
        errno = EINVAL;
        errmsg = "urgency must be between 0 and 31";
        goto error;
    }
    if (urgency > FLUX_JOB_URGENCY_DEFAULT
        && !(cred.rolemask & FLUX_ROLE_OWNER)) {
        errno = EPERM;
        errmsg = "urgency greater than 16 requires instance owner credentials";
        goto error;
    }
    if (ctx->users->empty ()
        || check_map_for_dne_only (*ctx->users, *ctx->users_def_bank)) {
        errno = EAGAIN;
        errmsg = "flux-accounting data has not been loaded into the "
                 "priority plugin yet";
        goto error;
    }

    // if no queue was requested, use Flux's default queue when one is found;
    // otherwise, leave queue NULL so the estimate has no queue factor
    if (queue == NULL && !ctx->default_queue->empty ())
        queue = ctx->default_queue->c_str ();

    results = json_array ();
    if (!results) {
        errno = ENOMEM;
        goto error;
    }

    if (all_banks) {
        auto user_it = ctx->users->find (cred.userid);

        if (user_it == ctx->users->end ()) {
            errno = ENOENT;
            errmsg = "cannot find user/bank or user/default bank entry "
                     "for caller";
            goto error;
        }
        for (auto &entry : user_it->second) {
            // skip the placeholder created by add_special_association ()
            if (entry.first == "DNE")
                continue;
            // calculate the estimated priority for this bank
            if (append_priority_estimate (results,
                                          ctx,
                                          &entry.second,
                                          queue,
                                          urgency) < 0) {
                errno = ENOMEM;
                goto error;
            }
        }
        if (json_array_size (results) == 0) {
            // the caller only has a placeholder association
            errno = EAGAIN;
            errmsg = "flux-accounting data for caller has not been loaded "
                     "into the priority plugin yet";
            goto error;
        }
    } else {
        Association *a = get_estimate_association (ctx, cred.userid, bank);
        if (a == nullptr) {
            errno = ENOENT;
            errmsg = "cannot find user/bank or user/default bank entry "
                     "for caller";
            goto error;
        }
        if (a->bank_name == "DNE") {
            // mirror priority_cb (), which keeps such a job in PRIORITY
            errno = EAGAIN;
            errmsg = "flux-accounting data for caller has not been loaded "
                     "into the priority plugin yet";
            goto error;
        }
        if (append_priority_estimate (results, ctx, a, queue, urgency) < 0) {
            errno = ENOMEM;
            goto error;
        }
    }

    if (flux_respond_pack (h, msg, "{s:O}", "priorities", results) < 0)
        flux_log_error (h, "flux_respond_pack");
    json_decref (results);
    return;
error:
    json_decref (results);
    if (flux_respond_error (h,
                            msg,
                            errno,
                            errmsg ? errmsg : flux_msg_last_error (msg)) < 0)
        flux_log_error (h, "flux_respond_error");
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
