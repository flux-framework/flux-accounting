/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* compute_hours_limits.cpp - tracks associations' usage across all of their
 * jobs.
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

#include <map>
#include <iterator>
#include <cmath>
#include <cassert>
#include <algorithm>
#include <cinttypes>
#include <vector>
#include <sstream>
#include <cstdint>
#include <iomanip>
#include <limits>
#include <unordered_map>
#include <iostream>

// custom job resource counting file
#include "jj.hpp"

// class to store runtimes for an Association's jobs as they enter through
// various states
class Job {
public:
    flux_jobid_t id = 0;
    double t_run = 0.0;
    int nnodes = 0;
    double expected_usage = 0.0;
};

// all attributes are per-association
class Association {
public:
    // attributes
    std::string username = "";
    int userid = 0;
    std::string bank = "";
    std::string default_bank = "";
    double current_usage = 0.0;
    double total_usage = 0.0;
    std::unordered_map<flux_jobid_t, Job> jobs;

    // remove a Job from an Association's "jobs" map
    void remove_job (flux_jobid_t jobid) {
        jobs.erase (jobid);
    }

    // get Job by job ID
    Job* get_job (flux_jobid_t jobid) {
        auto it = jobs.find (jobid);
        return (it != jobs.end()) ? &(it->second) : nullptr;
    }

    // convert an Association object to JSON string
    json_t *to_json () const;
};

// data structures to store association data from the flux-accounting DB
std::map<int, std::map<std::string, Association>> associations;
std::map<int, std::string> assoc_default_bank;

/******************************************************************************
 *                                                                            *
 *                            Helper Functions                                *
 *                                                                            *
 *****************************************************************************/
/*
 * Convert an Association object to a JSON object so it can be returned in the
 * output of "flux jobtap query".
 */
json_t* Association::to_json () const
{
    json_t *u = nullptr;
    json_t *jobs_json = nullptr;

    // create JSON object for the jobs map
    jobs_json = json_object ();
    if (!jobs_json)
        goto error;

    for (const auto &job_entry : jobs) {
        const Job &job = job_entry.second;
        json_t *job_json = json_pack ("{s:I, s:f, s:i, s:f}",
                                      "id", (json_int_t) job.id,
                                      "t_run", job.t_run,
                                      "nnodes", job.nnodes,
                                      "expected_usage", job.expected_usage);
        if (!job_json)
            goto error;

        // Use job id as string key
        char keybuf[32];
        snprintf (keybuf, sizeof(keybuf), "%ju", (uintmax_t) job.id);
        if (json_object_set_new (jobs_json, keybuf, job_json) < 0) {
            json_decref (job_json);
            goto error;
        }
    }

    u = json_pack ("{s:s, s:i, s:s, s:s, s:f, s:f, s:o}",
                   "username", username.c_str (),
                   "userid", userid,
                   "bank", bank.c_str (),
                   "default_bank", default_bank.c_str (),
                   "current_usage", current_usage,
                   "total_usage", total_usage,
                   "jobs", jobs_json);  // 'o' steals the reference

    if (!u)
        goto error;

    return u;

error:
    json_decref (jobs_json);
    json_decref (u);
    return nullptr;
}


/*
 * Convert an unordered_map of Association objects into a JSON object so it can
 * be returned in the output of "flux jobtap query".
 */
json_t* convert_map_to_json (std::map<int, std::map<std::string, Association>>
                                &users)
{
    json_t *accounting_data = json_array ();
    if (!accounting_data)
        return nullptr;

    // each Association in the users map is a pair; the first item is the
    // userid and the second is a list of banks they belong to
    for (const auto& association : users) {
        json_t *banks = json_array ();
        if (!banks) {
            json_decref (accounting_data);
            return nullptr;
        }
        for (const auto &bank : association.second) {
            // bank.second refers to an Association object
            json_t *b = bank.second.to_json ();
            if (!b || json_array_append_new (banks, b) < 0) {
                json_decref (accounting_data);
                json_decref (banks);
                return nullptr;
            }
        }

        json_t *u = json_pack ("{siso}",
                               "userid",
                               association.first,
                               "banks", banks);
        if (!u || json_array_append_new (accounting_data, u) < 0) {
            json_decref (accounting_data);
            json_decref (banks);
            return nullptr;
        }
    }

    return accounting_data;
}

/******************************************************************************
 *                                                                            *
 *                               Callbacks                                    *
 *                                                                            *
 *****************************************************************************/
/*
 * Reset the total_usage attribute for every association back to 0.0.
 */
 static void clear_cb (flux_t *h,
                      flux_msg_handler_t *mh,
                      const flux_msg_t *msg,
                      void *arg)
{
    for (auto &user_entry : associations) {
        for (auto &bank_entry : user_entry.second) {
            bank_entry.second.total_usage = 0.0;
        }
    }
}

 /*
 * Get the current state of every known Association in the plugin.
 */
static int query_cb (flux_plugin_t *p,
                     const char *topic,
                     flux_plugin_arg_t *args,
                     void *data)
{
    flux_t *h = flux_jobtap_get_flux (p);
    json_t *accounting_data = convert_map_to_json (associations);
    if (!accounting_data)
        return -1;

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "compute_hours_limits",
                              accounting_data) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "compute_hours_limits: query_cb: "
                        "flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (accounting_data);

    return 0;
}


 /*
 * Unpack a payload containing association data from the flux-accounting
 * database from an external bulk update service and place it in the
 * "associations" unordered_map.
 */
static void update_cb (flux_t *h,
                       flux_msg_handler_t *mh,
                       const flux_msg_t *msg,
                       void *arg)
{
    int userid;
    const char *username;
    const char *bank;
    const char *default_bank;

    json_t *data = NULL;
    json_error_t error;
    int num_data = 0;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid bulk_update payload");
        goto error;
    }
    num_data = json_array_size (data);

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0,
                            "{s:i, s:s, s:s, s:s}",
                            "userid", &userid,
                            "username", &username,
                            "bank", &bank,
                            "default_bank", &default_bank) < 0)
            flux_log (h, LOG_ERR, "compute_hours unpack: %s", error.text);

        Association *a;
        a = &associations[userid][bank];
        a->username = username;
        a->userid = userid;
        a->bank = bank;
        a->default_bank = default_bank;

        assoc_default_bank[userid] = default_bank;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


/*
 * Process a job in job.new and pack an Association object with the job so its
 * information can be later accessed to update requested and actual job usage.
 */
static int new_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid = 0;
    flux_jobid_t jobid = 0;
    const char *bank = NULL;
    Job *job;

    // unpack the required attributes to keep track of the job
    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:I, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "id", &jobid,
                                "jobspec", "attributes", "system",
                                "bank", &bank) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack attributes");
    }

    auto it = associations.find (userid);
    if (it == associations.end ()) {
        // association could not be found
        return -1;
    }

    std::string b;
    if (bank != NULL)
        b = bank;
    else
        // get the default bank of this user
        b = assoc_default_bank[userid];
    auto bank_it = it->second.find (b);
    if (bank_it == it->second.end ()) {
        // user does not have accounting information under the specified bank
        return -1;
    }

    Association *a = &bank_it->second;
    // create the Job object and store it in Association's "jobs" map
    job = &a->jobs[jobid];
    job->id = jobid;

    if (flux_jobtap_job_aux_set (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "compute_hours_limits:association_info",
                                 a,
                                 NULL) < 0) {
        flux_log_error (h, "flux_jobtap_job_aux_set");
    }

    return 0;
}


/*
 * Look at the requested duration and size of the job in job.state.depend.
 * Calculate the job's expected usage and store it in the Job object.
 */
static int depend_cb (flux_plugin_t *p,
                      const char *topic,
                      flux_plugin_arg_t *args,
                      void *data)
{
    json_t *jobspec = NULL;
    struct jj_counts counts;
    double duration = 0.0;
    flux_jobid_t jobid;
    Association *a;

    a = static_cast<Association *> (flux_jobtap_job_aux_get (
                                    p,
                                    FLUX_JOBTAP_CURRENT_JOB,
                                    "compute_hours_limits:association_info"));
    if (a == NULL) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.depend: association info is "
                                     "missing");

        return -1;
    }

    flux_t *h = flux_jobtap_get_flux (p);
    // unpack jobspec
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:I, s:o, s{s{s{s?F}}}}",
                                "id", &jobid,
                                "jobspec", &jobspec,
                                "jobspec", "attributes", "system",
                                "duration", &duration) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    // unpack specified counts from jobspec
    if (jj_get_counts_json (jobspec, &counts) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "jj_get_counts_json: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    Job *job = a->get_job (jobid);
    if (job == nullptr) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.depend: couldn't find job in "
                                     "Association's 'jobs' map");
        return -1;
    } else {
        job->nnodes = counts.nnodes;
        job->expected_usage = counts.nnodes * duration;
    }

    return 0;
}


/*
 * Store the timestamp of when the job entered RUN state in the Job object so
 * it's actual duration (and usage) can be calculated when the job finishes.
 * Add the job's expected usage to the Association's current_usage attribute.
 */
static int run_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    flux_jobid_t jobid;
    Association *a;
    double t_run = 0.0;

    flux_t *h = flux_jobtap_get_flux (p);
    // unpack jobspec
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:I, s:{s:F}}",
                                "id", &jobid,
                                "entry", "timestamp", &t_run) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    a = static_cast<Association *> (flux_jobtap_job_aux_get (
                                    p,
                                    FLUX_JOBTAP_CURRENT_JOB,
                                    "compute_hours_limits:association_info"));
    if (a == NULL) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.depend: association info is "
                                     "missing");

        return -1;
    }

    Job *job = a->get_job (jobid);
    if (job == nullptr) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.run: couldn't find Job in "
                                     "Association's 'jobs' map");
        return -1;
    } else {
        // store timestamp in Job object
        job->t_run = t_run;
    }
    // add anticipated usage to association's current usage
    a->current_usage += job->expected_usage;

    return 0;
}


/*
 * Calculate the job's actual usage and update the Association's current usage
 * and total usage.
 */
static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    double duration = 0.0;
    double t_inactive = 0.0;
    flux_jobid_t jobid;
    Association *a;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:I, s{s{s{s?F}}}, s:{s:F}}",
                                "id", &jobid,
                                "jobspec", "attributes", "system",
                                "duration", &duration,
                                "entry", "timestamp", &t_inactive) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    a = static_cast<Association *> (flux_jobtap_job_aux_get (
                                    p,
                                    FLUX_JOBTAP_CURRENT_JOB,
                                    "compute_hours_limits:association_info"));
    if (a == NULL) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.inactive: association info is "
                                     "missing");

        return -1;
    }

    Job *job = a->get_job (jobid);
    if (job == nullptr) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "compute_hours_limits",
                                     0,
                                     "job.state.inactive: couldn't find job in "
                                     "Association's 'jobs' map");
        return -1;
    }

    if (!flux_jobtap_job_event_posted (p, FLUX_JOBTAP_CURRENT_JOB, "alloc")) {
        // this job never ran, so just remove it from the Association's "jobs"
        // map and return
        a->remove_job (jobid);
        return 0;
    }

    // subtract the job's *expected* usage from the Association's current_usage
    // attribute
    a->current_usage -= job->expected_usage;
    // add the job's *actual* usage to the Association's total_usage attribute.
    a->total_usage += (job->nnodes * (t_inactive - job->t_run));
    // remove the job from the Association's "jobs" map
    a->remove_job (jobid);

    return 0;
}


static const struct flux_plugin_handler tab[] = {
    { "plugin.query", query_cb, NULL},
    { "job.new", new_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "job.state.depend", depend_cb, NULL },
    { "job.state.run", run_cb, NULL},
    { 0 },
};


extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    if (flux_plugin_register (p, "compute_hours_limits", tab) < 0
        || flux_jobtap_service_register (p, "update", update_cb, p) < 0
        || flux_jobtap_service_register (p, "clear", clear_cb, p) < 0)
        return -1;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
