/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* mycpppriority.cpp - custom basic job priority plugin
 *
 */

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}
#include <flux/core.h>
#include <flux/jobtap.h>
#include <map>
#include <iterator>
#include <cmath>
#include <cassert>
#include <algorithm>
#include <cinttypes>

std::map<int, std::map<std::string, double>> users;

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

    std::map<int, std::map<std::string, double>>::iterator it;
    std::map<std::string, double>::iterator inner_it;

    fshare_weight = 100000;

    if (urgency == FLUX_JOB_URGENCY_HOLD)
        return FLUX_JOB_PRIORITY_MIN;

    if (urgency == FLUX_JOB_URGENCY_EXPEDITE)
        return FLUX_JOB_PRIORITY_MAX;

    // search element in map of maps by key
    it = users.find (userid);

    // search for correct fshare value using passed-in bank; otherwise, use
    // a default bank
    if (bank != NULL) {
        inner_it = it->second.find (bank);
        fshare_factor = inner_it->second;
    }
    else {
        inner_it = it->second.find ("default");
        fshare_factor = inner_it->second;
    }

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
    char *uid, *fshare, *bank;

    if (flux_request_unpack (msg, NULL, "{s:s, s:s, s:s}",
                             "userid", &uid,
                             "bank", &bank,
                             "fairshare", &fshare) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");

    // if the user being added to the does not yet have any entries in the map,
    // treat their first bank as the "default" bank
    if (users.count (std::atoi (uid)) == 0)
        users[std::atoi (uid)]["default"] = std::stod (fshare);

    users[std::atoi (uid)][bank] = std::stod (fshare);

    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


/*
 * Unpack the urgency and userid from a submitted job and call calc_priority (),
 * which will return a new job priority to be packed.
 */
static int priority_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int urgency, userid;
    char *bank = NULL;
    int64_t priority;

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
    std::map<int, std::map<std::string, double>>::iterator it;
    std::map<std::string, double>::iterator inner_it;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    // searching element in std::map by key
    it = users.find (userid);
    if (it == users.end ())
        return flux_jobtap_reject_job (p, args,
                                       "user not found in flux-accounting DB");

    if (bank != NULL) {
        inner_it = it->second.find (std::string (bank));
        if (inner_it == it->second.end ())
            return flux_jobtap_reject_job (p, args,
                                    "user does not belong to specified bank");
    }

    return 0;
}


static const struct flux_plugin_handler tab[] = {
    { "job.validate", validate_cb, NULL },
    { "job.state.priority", priority_cb, NULL },
    { "job.priority.get", priority_cb, NULL },
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
