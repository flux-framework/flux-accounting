/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* mf_priority.cpp - custom basic job priority plugin
 *
 */

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
#include <map>
#include <iterator>
#include <cmath>
#include <cassert>
#include <algorithm>
#include <cinttypes>
#include <vector>

std::map<int, std::map<std::string, struct bank_info>> users;
std::map<int, std::string> users_def_bank;

struct bank_info {
    double fairshare;
    int max_run_jobs;
    int cur_run_jobs;
    std::vector<long int> held_jobs;
};

/******************************************************************************
 *                                                                            *
 *                           Helper Functions                                 *
 *                                                                            *
 *****************************************************************************/

/*
 * Calculate a user's job priority using the following factors:
 *
 * fairshare: the ratio between the amount of resources allocated vs. resources
 *     consumed.
 * urgency: a user-controlled factor to prioritize their own jobs.
 */
int64_t priority_calculation (flux_plugin_t *p,
                              flux_plugin_arg_t *args,
                              int userid,
                              char *bank,
                              int urgency)
{
    double fshare_factor = 0.0, priority = 0.0;
    int fshare_weight;
    struct bank_info *b;

    fshare_weight = 100000;

    if (urgency == FLUX_JOB_URGENCY_HOLD)
        return FLUX_JOB_PRIORITY_MIN;

    if (urgency == FLUX_JOB_URGENCY_EXPEDITE)
        return FLUX_JOB_PRIORITY_MAX;

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.priority: bank info is " \
                                     "missing");
        return -1;
    }

    fshare_factor = b->fairshare;

    priority = (fshare_weight * fshare_factor) + (urgency - 16);

    return abs (round (priority));
}


/******************************************************************************
 *                                                                            *
 *                               Callbacks                                    *
 *                                                                            *
 *****************************************************************************/

/*
 * Unpack a payload from an external bulk update service and place it in the
 * multimap datastructure.
 */
static void rec_update_cb (flux_t *h,
                           flux_msg_handler_t *mh,
                           const flux_msg_t *msg,
                           void *arg)
{
    char *bank, *def_bank = NULL;
    int uid, max_running_jobs = 0;
    double fshare = 0.0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid bulk_update payload");
        goto error;
    }
    num_data = json_array_size (data);

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0, "{s:i, s:s, s:s, s:F, s:i}",
                            "userid", &uid,
                            "bank", &bank,
                            "def_bank", &def_bank,
                            "fairshare", &fshare,
                            "max_running_jobs", &max_running_jobs) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        struct bank_info *b;
        b = &users[uid][bank];

        b->fairshare = fshare;
        b->max_run_jobs = max_running_jobs;

        users_def_bank[uid] = def_bank;
    }

    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


/*
 * Unpack the urgency and userid from a submitted job and call
 * priority_calculation (), which will return a new job priority to be packed.
 */
static int priority_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int urgency, userid;
    char *bank = NULL;
    int64_t priority;
    struct bank_info *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:i, s{s{s{s?s}}}}",
                                "urgency", &urgency,
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    priority = priority_calculation (p, args, userid, bank, urgency);

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:I}",
                              "priority",
                              priority) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_pack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.priority: bank info is " \
                                     "missing");

        return -1;
    }

    b->cur_run_jobs++;

    return 0;
}


/*
 * Look up the userid of the submitted job in the multimap; if user is not found
 * in the map, reject the job saying the user wasn't found in the
 * flux-accounting database.
 */
static int validate_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    char *bank = NULL;
    int max_run_jobs = 0;
    double fairshare = 0.0;

    std::map<int, std::map<std::string, struct bank_info>>::iterator it;
    std::map<std::string, struct bank_info>::iterator bank_it;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    // make sure user belongs to flux-accounting DB
    it = users.find (userid);
    if (it == users.end ())
        return flux_jobtap_reject_job (p, args,
                                       "user not found in flux-accounting DB");

    // make sure user belongs to bank they specified; if no bank was passed in,
    // look up their default bank
    if (bank != NULL) {
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return flux_jobtap_reject_job (p, args,
                                     "user does not belong to specified bank");
    } else {
        bank = const_cast<char*> (users_def_bank[userid].c_str ());
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return flux_jobtap_reject_job (p, args,
                                     "user/default bank entry does not exist");
    }

    max_run_jobs = bank_it->second.max_run_jobs;
    fairshare = bank_it->second.fairshare;

    // if a user's fairshare value is 0, that means they shouldn't be able
    // to run jobs on a system
    if (fairshare == 0)
        return flux_jobtap_reject_job (p, args, "user fairshare value is 0");

    // special case where the user/bank bank_info struct is set to NULL; used
    // for testing the "if (b == NULL)" checks
    if (max_run_jobs == -1) {
        if (flux_jobtap_job_aux_set (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority:bank_info",
                                     NULL,
                                     NULL) < 0)
            flux_log_error (h, "flux_jobtap_job_aux_set");

        return 0;
    }


    if (flux_jobtap_job_aux_set (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "mf_priority:bank_info",
                                 &bank_it->second,
                                 NULL) < 0)
        flux_log_error (h, "flux_jobtap_job_aux_set");

    return 0;
}


static int depend_cb (flux_plugin_t *p,
                      const char *topic,
                      flux_plugin_arg_t *args,
                      void *data)
{
    int userid;
    long int id;
    struct bank_info *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:I}",
                                "userid", &userid, "id", &id) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.depend: bank info is " \
                                     "missing");

        return -1;
    }

    // if user has already hit their max running jobs count, add a job
    // dependency to hold job until an already running job has finished
    if ((b->max_run_jobs > 0) && (b->cur_run_jobs == b->max_run_jobs)) {
        if (flux_jobtap_dependency_add (p, id, "max-jobs-limit") < 0) {
            flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority", 0, "failed to add " \
                                         "job dependency");

            return -1;
        }
        b->held_jobs.push_back (id);
    }

    return 0;
}


static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    struct bank_info *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i}",
                                "userid", &userid) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.inactive: bank info is " \
                                     "missing");

        return -1;
    }

    b->cur_run_jobs--;

    // if the user/bank combo has any currently held jobs and the user is now
    // under their max jobs limit, remove the dependency from first held job
    if ((b->held_jobs.size () > 0) && (b->cur_run_jobs < b->max_run_jobs)) {
        long int jobid = b->held_jobs.front ();

        if (flux_jobtap_dependency_remove (p, jobid, "max-jobs-limit") < 0)
            flux_jobtap_raise_exception (p, jobid, "mf_priority",
                                         0, "failed to remove job dependency");

        b->held_jobs.erase (b->held_jobs.begin ());
    }

    return 0;
}


static const struct flux_plugin_handler tab[] = {
    { "job.validate", validate_cb, NULL },
    { "job.state.priority", priority_cb, NULL },
    { "job.priority.get", priority_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "job.state.depend", depend_cb, NULL },
    { 0 },
};


extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    if (flux_plugin_register (p, "mf_priority", tab) < 0
        || flux_jobtap_service_register (p, "rec_update", rec_update_cb, p) < 0)
        return -1;
    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
