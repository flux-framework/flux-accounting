/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* resource_quotas.cpp - track and limit concurrent resource usage
 *
 * Track per-user resource usage for every resource type found in the
 * jobspec of running jobs, including custom types. Usage is added when
 * a job starts running and removed when it becomes inactive, and the
 * tracked state can be inspected with flux jobtap query.
 */

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#include <map>
#include <string>

#include "jj.hpp"

// the total amount of each resource type in use by the running jobs of
// each user, keyed by userid and then by resource type name
std::map<int, std::map<std::string, int>> user_resources;

/*
 * Unpack the userid and jobspec for the current job and count the total
 * resources the job requests. Returns 0 on success. Returns -1 and raises
 * a job exception if the jobspec cannot be counted.
 */
static int get_job_resources (flux_plugin_t *p,
                              const char *topic,
                              flux_plugin_arg_t *args,
                              int &userid,
                              jj_counts &counts)
{
    json_t *jobspec = NULL;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:o}",
                                "userid", &userid,
                                "jobspec", &jobspec) < 0) {
        flux_log (flux_jobtap_get_flux (p),
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }
    if (jj_get_counts_json (jobspec, counts) < 0) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "resource_quotas",
                                     0,
                                     "%s: failed to count job resources: %s",
                                     topic,
                                     counts.error.c_str ());
        return -1;
    }
    return 0;
}

// add the resource totals of a job to the usage of the user that
// submitted it
static void add_resources (int userid, const jj_counts &counts)
{
    for (const auto &entry : counts.counts)
        user_resources[userid][entry.first] += entry.second;
}

/*
 * A new job was introduced to the plugin. This fires at submission for
 * new jobs and also once for every active job when the plugin is loaded.
 * If the job is already running it is counted here, since its run
 * callback fired before this plugin was loaded.
 */
static int new_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid;
    flux_job_state_t state;
    jj_counts counts;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i}",
                                "state", &state) < 0) {
        flux_log (flux_jobtap_get_flux (p),
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }
    if (state != FLUX_JOB_STATE_RUN)
        return 0;

    if (get_job_resources (p, topic, args, userid, counts) < 0)
        return -1;
    add_resources (userid, counts);

    return 0;
}

/*
 * A job has started running. Add its resource totals to the usage of the
 * user that submitted it.
 */
static int run_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid;
    jj_counts counts;

    if (get_job_resources (p, topic, args, userid, counts) < 0)
        return -1;
    add_resources (userid, counts);

    return 0;
}

/*
 * A job has become inactive. If it was running, subtract its resource
 * totals from the usage of the user that submitted it. Entries that reach
 * zero are removed so the tracked state only contains users with running
 * jobs.
 */
static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    jj_counts counts;

    // a job that never received an allocation was never counted
    if (!flux_jobtap_job_event_posted (p, FLUX_JOBTAP_CURRENT_JOB, "alloc"))
        return 0;

    if (get_job_resources (p, topic, args, userid, counts) < 0)
        return -1;

    auto user = user_resources.find (userid);
    if (user == user_resources.end ())
        return 0;
    for (const auto &entry : counts.counts) {
        auto usage = user->second.find (entry.first);
        if (usage == user->second.end ())
            continue;
        usage->second -= entry.second;
        if (usage->second <= 0)
            user->second.erase (usage);
    }
    if (user->second.empty ())
        user_resources.erase (user);

    return 0;
}

// build a JSON object of every user's tracked resource usage
static json_t *user_resources_to_json ()
{
    json_t *o = json_object ();
    if (!o)
        return NULL;
    for (const auto &user : user_resources) {
        json_t *usage = json_object ();
        if (!usage)
            goto error;
        for (const auto &entry : user.second) {
            if (json_object_set_new (usage,
                                     entry.first.c_str (),
                                     json_integer (entry.second)) < 0) {
                json_decref (usage);
                goto error;
            }
        }
        if (json_object_set_new (o,
                                 std::to_string (user.first).c_str (),
                                 usage) < 0) {
            json_decref (usage);
            goto error;
        }
    }
    return o;
error:
    json_decref (o);
    return NULL;
}

/*
 * Report the tracked per-user resource usage so it can be inspected with
 * flux jobtap query.
 */
static int query_cb (flux_plugin_t *p,
                     const char *topic,
                     flux_plugin_arg_t *args,
                     void *data)
{
    json_t *usage = user_resources_to_json ();

    if (!usage)
        return -1;

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "user_resources",
                              usage) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "resource_quotas: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (usage);

    return 0;
}

static const struct flux_plugin_handler tab[] = {
    { "job.new", new_cb, NULL },
    { "job.state.run", run_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "plugin.query", query_cb, NULL },
    { 0 },
};

extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    // explicitly reset all tracked state so a reload starts clean and is
    // rebuilt from the active jobs replayed by the job manager
    user_resources.clear ();

    if (flux_plugin_register (p, "resource_quotas", tab) < 0)
        return -1;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
