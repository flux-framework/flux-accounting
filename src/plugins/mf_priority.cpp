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

// custom bank_info class file
#include "accounting.hpp"

// the plugin does not know about the association who submitted a job and will
// assign default values to the association until it receives information from
// flux-accounting
#define BANK_INFO_MISSING 999

// a queue is specified for a submitted job that flux-accounting does not know
// about
#define UNKNOWN_QUEUE 0

// no queue is specified for a submitted job
#define NO_QUEUE_SPECIFIED 0

// a queue was specified for a submitted job that flux-accounting knows about and
// the association does not have permission to run jobs under
#define INVALID_QUEUE -6

// different codes to return as a result of looking up user/bank information:
//
// BANK_SUCCESS: we found an entry for the passed-in user/bank
// BANK_USER_NOT_FOUND: the user could not be found in the plugin map
// BANK_INVALID: the user specified a bank they don't belong to
// BANK_NO_DEFAULT: the user does not have a default bank in the plugin map
enum bank_info_codes {
    BANK_SUCCESS,
    BANK_USER_NOT_FOUND,
    BANK_INVALID,
    BANK_NO_DEFAULT
};

typedef std::pair<bank_info_codes, std::map<std::string, Association>::iterator> bank_info_result;

std::map<int, std::map<std::string, Association>> users;
std::map<std::string, struct queue_info> queues;
std::map<int, std::string> users_def_bank;

// min_nodes_per_job, max_nodes_per_job, and max_time_per_job are not
// currently used or enforced in this plugin, so their values have no
// effect in queue limit enforcement.
struct queue_info {
    int min_nodes_per_job;
    int max_nodes_per_job;
    int max_time_per_job;
    int priority;
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
 *
 * urgency: a user-controlled factor to prioritize their own jobs.
 *
 * queue: a factor that can further affect the priority of a job based on the
 *     queue passed in.
 */
int64_t priority_calculation (flux_plugin_t *p,
                              flux_plugin_arg_t *args,
                              int userid,
                              char *bank,
                              int urgency)
{
    double fshare_factor = 0.0, priority = 0.0;
    int queue_factor = 0;
    int fshare_weight, queue_weight;
    Association *b;

    fshare_weight = 100000;
    queue_weight = 10000;

    if (urgency == FLUX_JOB_URGENCY_HOLD)
        return FLUX_JOB_PRIORITY_MIN;

    if (urgency == FLUX_JOB_URGENCY_EXPEDITE)
        return FLUX_JOB_PRIORITY_MAX;

    b = static_cast<Association *> (flux_jobtap_job_aux_get (
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
    queue_factor = b->queue_factor;

    priority = round ((fshare_weight * fshare_factor) +
                      (queue_weight * queue_factor) +
                      (urgency - 16));

    if (priority < 0)
        return FLUX_JOB_PRIORITY_MIN;

    return priority;
}


static int get_queue_info (char *queue,
                           std::vector<std::string> permissible_queues)
{
    std::map<std::string, struct queue_info>::iterator q_it;

    // make sure that if a queue is passed in, it is a valid queue for the
    // user to run jobs in
    if (queue != NULL) {
        // check #1) the queue passed in exists in the queues map;
        // if the queue cannot be found, this means that flux-accounting
        // does not know about the queue, and thus should return a default
        // factor
        q_it = queues.find (queue);
        if (q_it == queues.end ())
            return UNKNOWN_QUEUE;

        // check #2) the queue passed in is a valid option to pass for user
        std::vector<std::string>::iterator vect_it;
        vect_it = std::find (permissible_queues.begin (),
                             permissible_queues.end (), queue);

        if (vect_it == permissible_queues.end ())
            return INVALID_QUEUE;
        else
            // add priority associated with the passed in queue to bank_info
            return queues[queue].priority;
    } else {
        // no queue was specified, so just use a default queue factor
        return NO_QUEUE_SPECIFIED;
    }
}


static void split_string (char *queues, Association *b)
{
    std::stringstream s_stream;

    s_stream << queues; // create string stream from string
    while (s_stream.good ()) {
        std::string substr;
        getline (s_stream, substr, ','); // get string delimited by comma
        b->queues.push_back (substr);
    }
}


int check_queue_factor (flux_plugin_t *p,
                        int queue_factor,
                        char *queue,
                        char *prefix = (char *) "")
{
    if (queue_factor == INVALID_QUEUE) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "%sQueue not valid for user: %s",
                                     prefix, queue);
        return -1;
    }

    return 0;
}


// Scan the users map and look at each user's default bank to see if any one
// of them have a valid bank (i.e one that is not "DNE"; if any of the users do
// do have a valid bank, it will return false)
static bool check_map_for_dne_only ()
{
    // the users map iterated through in this for-loop, along with the
    // users_def_bank map used to look up a user's default bank, are
    // both global variables
    for (const auto& entry : users) {
        auto def_bank_it = users_def_bank.find(entry.first);
        if (def_bank_it != users_def_bank.end() &&
                def_bank_it->second != "DNE")
            return false;
    }

    return true;
}


/*
 * Update the jobspec with the default bank the association used to
 * submit their job under.
 */
static int update_jobspec_bank (flux_plugin_t *p, int userid)
{
    char *bank = NULL;
    std::map<int, std::map<std::string, Association>>::iterator it;

    it = users.find (userid);
    if (it == users.end ()) {
        return -1;
    }

    // look up default bank
    bank = const_cast<char*> (users_def_bank[userid].c_str ());

    // post jobspec-update event
    if (flux_jobtap_jobspec_update_pack (p,
                                         "{s:s}",
                                         "attributes.system.bank",
                                         bank) < 0)
        return -1;

    return 0;
}


// Given a userid and an optional bank, locate the associated information in
// the plugin's internal users map. The return value is a pair: the first value
// is a return code to indicate success or the type of failure, and the second
// value is an iterator that points to the appropriate user/bank's information
// associated with the submitted job
static bank_info_result get_bank_info (int userid, char *bank)
{
    std::map<int, std::map<std::string, Association>>::iterator it;
    std::map<std::string, Association>::iterator bank_it;

    it = users.find (userid);
    if (it == users.end ()) {
        return {BANK_USER_NOT_FOUND, bank_it};
    }

    // make sure user belongs to bank they specified; if no bank was passed in,
    // look up their default bank
    if (bank != NULL) {
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return {BANK_INVALID, bank_it};
    } else {
        bank = const_cast<char*> (users_def_bank[userid].c_str ());
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return {BANK_NO_DEFAULT, bank_it};
    }

    return {BANK_SUCCESS, bank_it};
}


/******************************************************************************
 *                                                                            *
 *                               Callbacks                                    *
 *                                                                            *
 *****************************************************************************/

/*
 * Get state of all user and bank information from plugin
 */
static int query_cb (flux_plugin_t *p,
                     const char *topic,
                     flux_plugin_arg_t *args,
                     void *data)
{
    flux_t *h = flux_jobtap_get_flux (p);
    json_t *accounting_data = convert_map_to_json (users);

    if (!accounting_data)
        return -1;

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "mf_priority_map",
                              accounting_data) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "mf_priority: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (accounting_data);

    return 0;
}


/*
 * Unpack a payload from an external bulk update service and place it in the
 * multimap datastructure.
 */
static void rec_update_cb (flux_t *h,
                           flux_msg_handler_t *mh,
                           const flux_msg_t *msg,
                           void *arg)
{
    char *bank, *def_bank, *assoc_queues = NULL;
    int uid, max_running_jobs, max_active_jobs = 0;
    double fshare = 0.0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;
    int active = 1;
    std::stringstream s_stream;

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

        if (json_unpack_ex (el, &error, 0,
                            "{s:i, s:s, s:s, s:F, s:i, s:i, s:s, s:i}",
                            "userid", &uid,
                            "bank", &bank,
                            "def_bank", &def_bank,
                            "fairshare", &fshare,
                            "max_running_jobs", &max_running_jobs,
                            "max_active_jobs", &max_active_jobs,
                            "queues", &assoc_queues,
                            "active", &active) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        Association *b;
        b = &users[uid][bank];

        b->bank_name = bank;
        b->fairshare = fshare;
        b->max_run_jobs = max_running_jobs;
        b->max_active_jobs = max_active_jobs;
        b->active = active;

        // split queues comma-delimited string and add it to b->queues vector
        b->queues.clear ();
        split_string_and_push_back (assoc_queues, b->queues);

        users_def_bank[uid] = def_bank;
    }

    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}

/*
 * Unpack a payload from an external bulk update service and place it in the
 * multimap datastructure.
 */
static void rec_q_cb (flux_t *h,
                      flux_msg_handler_t *mh,
                      const flux_msg_t *msg,
                      void *arg)
{
    char *queue = NULL;
    int min_nodes_per_job, max_nodes_per_job, max_time_per_job, priority = 0;
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
        flux_log (h, LOG_ERR, "mf_priority: invalid queue info payload");
        goto error;
    }
    num_data = json_array_size (data);

    // clear queues map
    queues.clear ();

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0,
                            "{s:s, s:i, s:i, s:i, s:i}",
                            "queue", &queue,
                            "min_nodes_per_job", &min_nodes_per_job,
                            "max_nodes_per_job", &max_nodes_per_job,
                            "max_time_per_job", &max_time_per_job,
                            "priority", &priority) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        struct queue_info *q;
        q = &queues[queue];

        q->min_nodes_per_job = min_nodes_per_job;
        q->max_nodes_per_job = max_nodes_per_job;
        q->max_time_per_job = max_time_per_job;
        q->priority = priority;
    }

    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


static void reprior_cb (flux_t *h,
                        flux_msg_handler_t *mh,
                        const flux_msg_t *msg,
                        void *arg)
{
    flux_plugin_t *p = (flux_plugin_t*) arg;

    if (flux_jobtap_reprioritize_all (p) < 0)
        goto error;
    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
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
    char *queue = NULL;
    int64_t priority;
    Association *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:i, s{s{s{s?s, s?s}}}}",
                                "urgency", &urgency,
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    b = static_cast<Association *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "internal error: bank info is missing");

        return -1;
    }

    std::map<int, std::map<std::string, Association>>::iterator it;
    std::map<std::string, Association>::iterator bank_it;

    if (b->max_run_jobs == BANK_INFO_MISSING) {
        // try to look up user again
        it = users.find (userid);
        if (it == users.end () || check_map_for_dne_only () == true) {
            // the plugin could still be waiting on flux-accounting data
            // to be loaded in; keep the job in PRIORITY state
            return flux_jobtap_priority_unavail (p, args);
        } else {
            // make sure user belongs to bank they specified; if no bank was
            // passed in, look up their default bank
            if (bank != NULL) {
                bank_it = it->second.find (std::string (bank));
                if (bank_it == it->second.end ()) {
                    flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                                 "mf_priority", 0,
                                                 "not a member of %s", bank);
                    return -1;
                }
            } else {
                bank = const_cast<char*> (users_def_bank[userid].c_str ());
                bank_it = it->second.find (std::string (bank));
                if (bank_it == it->second.end ()) {
                    flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                                 "mf_priority", 0,
                                                 "user/default bank entry "
                                                 "does not exist");
                    return -1;
                }
            }

            if (bank_it->second.max_run_jobs == BANK_INFO_MISSING) {
                return flux_jobtap_priority_unavail (p, args);
            }

            // fetch priority associated with passed-in queue (or default queue)
            bank_it->second.queue_factor = get_queue_info (queue,
                                                           bank_it->second.queues);
            if (check_queue_factor (p,
                                    bank_it->second.queue_factor,
                                    queue) < 0)
                return -1;

            // if we get here, the bank was unknown when this job was first
            // accepted, and therefore the active job counts for this
            // job need to be incremented here
            bank_it->second.cur_active_jobs++;

            // update current job with user/bank information
            if (flux_jobtap_job_aux_set (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority:bank_info",
                                         &bank_it->second,
                                         NULL) < 0)
                flux_log_error (h, "flux_jobtap_job_aux_set");

            // now that we know the user/bank info associated with this job,
            // we need to update jobspec with the default bank used to
            // submit this job under
            if (update_jobspec_bank (p, userid) < 0) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "failed to update jobspec "
                                             "with bank name");
                return -1;
            }
        }
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


static void add_missing_bank_info (flux_plugin_t *p, flux_t *h, int userid)
{
    Association *b;

    b = &users[userid]["DNE"];
    users_def_bank[userid] = "DNE";

    b->bank_name = "DNE";
    b->fairshare = 0.1;
    b->max_run_jobs = BANK_INFO_MISSING;
    b->cur_run_jobs = 0;
    b->max_active_jobs = 1000;
    b->cur_active_jobs = 0;
    b->active = 1;
    b->held_jobs = std::vector<long int>();

    if (flux_jobtap_job_aux_set (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "mf_priority:bank_info",
                                 b,
                                 NULL) < 0)
        flux_log_error (h, "flux_jobtap_job_aux_set");
}


/*
 * Perform basic validation of a user/bank's submitted job. If a bank or
 * queue is specified on submission, ensure that the user is allowed to
 * submit a job under them. Check the active job limits for the user/bank
 * on submission as well to make sure that they are under this limit when
 * the job is submitted.
 *
 * This callback will also make sure that the user/bank belongs to
 * the flux-accounting DB; there are two behaviors supported here:
 *
 * if the plugin has SOME data about users/banks and the user does not have
 * an entry in the plugin, the job will be rejected.
 *
 * if the plugin has NO data about users/banks and the user does not have an
 * entry in the plugin, the job will be held until data is received by the
 * plugin.
 */
static int validate_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    char *bank = NULL;
    char *queue = NULL;
    flux_job_state_t state;
    int max_run_jobs, cur_active_jobs, max_active_jobs, queue_factor = 0;
    double fairshare = 0.0;
    bool only_dne_data;
    Association *a;

    // unpack the attributes of the user/bank's submitted job when it
    // enters job.validate and place them into their respective variables
    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:i, s{s{s{s?s, s?s}}}}",
                                "userid", &userid,
                                "state", &state,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    // perform a lookup in the users map of the unpacked user/bank
    a = get_association (userid, bank, users, users_def_bank);

    if (a == nullptr) {
        // the assocation could not be found in the plugin's internal map,
        // so perform a check to see if the map has any loaded
        // flux-accounting data before rejecting the job
        bool only_dne_data = check_map_for_dne_only ();

        if (users.empty () || only_dne_data) {
            add_missing_bank_info (p, h, userid);
            return 0;
        } else {
            return flux_jobtap_reject_job (p,
                                           args,
                                           "cannot find user/bank or "
                                           "user/default bank entry "
                                           "for uid: %i", userid);
        }
    }

    if (a->active == 0)
        // the association entry was disabled; reject the job
        return flux_jobtap_reject_job (p, args, "user/bank entry has been "
                                       "disabled from flux-accounting DB");

    if (get_queue_info (queue, a->queues) == INVALID_QUEUE)
        // the user/bank specified a queue that they do not belong to;
        // reject the job
        return flux_jobtap_reject_job (p, args, "Queue not valid for user: %s",
                                       queue);

    cur_active_jobs = a->cur_active_jobs;
    max_active_jobs = a->max_active_jobs;

    if (state == FLUX_JOB_STATE_NEW) {
        if (max_active_jobs > 0 && cur_active_jobs >= max_active_jobs)
            // the association is already at their max_active_jobs limit;
            // reject the job
            return flux_jobtap_reject_job (p,
                                           args,
                                           "user has max active jobs");
    }

    return 0;
}


/*
 * Create an Association object to be associated with the job submitted.
 * This object contains things like active and running jobs limits, the
 * association's fair share value, and associated priorities with a
 * passed-in queue.
 *
 * If an association is submitting a job under their default bank, update the
 * jobspec for this job to contain the bank name as well.
 */
static int new_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    char *bank = NULL;
    char *queue = NULL;
    int max_run_jobs, cur_active_jobs, max_active_jobs = 0;
    Association *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s, s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    b = static_cast<Association *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == nullptr) {
        // Association object was not unpacked; perform lookup
        b = get_association (userid, bank, users, users_def_bank);

        if (b == nullptr) {
            // the association could not be found in internal map, so create a
            // special Association object that will hold the job in PRIORITY
            add_missing_bank_info (p, h, userid);
            return 0;
        }

        if (bank == NULL) {
            // this job is meant to run under the association's default bank;
            // as a result, update the jobspec with their default bank name
            if (update_jobspec_bank (p, userid) < 0) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                            "mf_priority", 0,
                                            "failed to update jobspec "
                                            "with bank name");
                return -1;
            }
        }
    }

    // assign priority associated with validated queue
    b->queue_factor = get_queue_info (queue, b->queues);

    max_run_jobs = b->max_run_jobs;
    cur_active_jobs = b->cur_active_jobs;
    max_active_jobs = b->max_active_jobs;

    if (max_active_jobs > 0 && cur_active_jobs >= max_active_jobs)
        // the association is already at their max_active_jobs limit;
        // reject the job
        return flux_jobtap_reject_job (p, args, "user has max active jobs");

    if (max_run_jobs == -1) {
        // special case where the object passed between callbacks is set to
        // NULL; this is used for testing the "if (b == NULL)" checks
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
                                 b,
                                 NULL) < 0)
        flux_log_error (h, "flux_jobtap_job_aux_set");

    // increment the association's active jobs count
    b->cur_active_jobs++;

    return 0;
}


static int depend_cb (flux_plugin_t *p,
                      const char *topic,
                      flux_plugin_arg_t *args,
                      void *data)
{
    int userid;
    long int id;
    Association *b;

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

    b = static_cast<Association *> (flux_jobtap_job_aux_get (
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
        if (flux_jobtap_dependency_add (p,
                                        id,
                                        "max-running-jobs-user-limit") < 0) {
            flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority", 0, "failed to add " \
                                         "job dependency");

            return -1;
        }
        b->held_jobs.push_back (id);
    }

    return 0;
}


static int run_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid;
    Association *b;

    b = static_cast<Association *>
        (flux_jobtap_job_aux_get (p,
                                  FLUX_JOBTAP_CURRENT_JOB,
                                  "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.run: bank info is " \
                                     "missing");

        return -1;
    }

    // increment the user's current running jobs count
    b->cur_run_jobs++;

    return 0;
}


/*
 *  apply an update on a job with regard to its queue once it has been
 *  validated.
 */
static int job_updated (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    std::map<std::string, Association>::iterator bank_it;
    int userid;
    char *bank = NULL;
    char *queue = NULL;
    Association *b;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s}}}, s:{s?s}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system", "bank", &bank,
                                "updates",
                                    "attributes.system.queue", &queue) < 0)
        return flux_jobtap_error (p, args, "unable to unpack plugin args");

    // grab bank_info struct for user/bank (if any)
    b = static_cast<Association *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.update: bank info is missing");

        return -1;
    }

    // look up user/bank info based on unpacked information
    bank_info_result lookup_result = get_bank_info (userid, bank);

    if (lookup_result.first == BANK_USER_NOT_FOUND) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "job.update: cannot find info for user: ",
                                     userid);
    } else if (lookup_result.first == BANK_INVALID) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "job.update: not a member of %s",
                                     bank);
    } else if (lookup_result.first == BANK_NO_DEFAULT) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "job.update: user/default bank "
                                     "entry does not exist");
    } else if (lookup_result.first == BANK_SUCCESS) {
        bank_it = lookup_result.second;
    }

    // if the queue for the job has been updated, fetch the priority of the
    // validated queue and assign it to the associated bank_info struct
    if (queue != NULL) {
        int queue_factor = get_queue_info (queue, bank_it->second.queues);
        b->queue_factor = queue_factor;
    }

    return 0;
}


/*
 *  check for an updated queue and validate it for a user/bank; if the
 *  user/bank does not have access to the queue they are trying to update
 *  their job for, reject the update and keep the job in its current queue.
 */
static int update_queue_cb (flux_plugin_t *p,
                            const char *topic,
                            flux_plugin_arg_t *args,
                            void *data)
{
    std::map<std::string, Association>::iterator bank_it;
    int userid;
    char *bank = NULL;
    char *queue = NULL;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:s, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "value", &queue,
                                "jobspec", "attributes", "system", "bank",
                                &bank) < 0)
        return flux_jobtap_error (p, args, "unable to unpack plugin args");

    // look up user/bank info based on unpacked information
    bank_info_result lookup_result = get_bank_info (userid, bank);

    if (lookup_result.first == BANK_USER_NOT_FOUND) {
        return flux_jobtap_error (p,
                                  args,
                                  "mf_priority: cannot find info for user ",
                                  userid);
    } else if (lookup_result.first == BANK_INVALID) {
        return flux_jobtap_error (p,
                                  args,
                                  "mf_priority: not a member of %s",
                                  bank);
    } else if (lookup_result.first == BANK_NO_DEFAULT) {
        return flux_jobtap_error (p,
                                  args,
                                  "mf_priority: user/default bank entry does "
                                  "not exist");
    } else if (lookup_result.first == BANK_SUCCESS) {
        bank_it = lookup_result.second;

        // validate the updated queue and make sure the user/bank has
        // access to it; if not, reject the update
        if (get_queue_info (queue, bank_it->second.queues) == INVALID_QUEUE)
            return flux_jobtap_error (p,
                                      args,
                                      "mf_priority: queue not valid for user: %s",
                                      queue);
    }

    return 0;
}


static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    Association *b;
    std::map<int, std::map<std::string, Association>>::iterator it;
    std::map<std::string, Association>::iterator bank_it;

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

    b = static_cast<Association *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.inactive: bank info is " \
                                     "missing");

        return -1;
    }

    b->cur_active_jobs--;
    // nothing more to do if this job was never running
    if (!flux_jobtap_job_event_posted (p, FLUX_JOBTAP_CURRENT_JOB, "alloc"))
        return 0;

    // this job was running, so decrement the current running jobs count
    // and look to see if any held jobs can be released
    b->cur_run_jobs--;

    // if the user/bank combo has any currently held jobs and the user is now
    // under their max jobs limit, remove the dependency from first held job
    if ((b->held_jobs.size () > 0) && (b->cur_run_jobs < b->max_run_jobs)) {
        long int jobid = b->held_jobs.front ();

        if (flux_jobtap_dependency_remove (p,
                                           jobid,
                                           "max-running-jobs-user-limit") < 0)
            flux_jobtap_raise_exception (p, jobid, "mf_priority",
                                         0, "failed to remove job dependency");

        b->held_jobs.erase (b->held_jobs.begin ());
    }

    return 0;
}


static const struct flux_plugin_handler tab[] = {
    { "job.validate", validate_cb, NULL },
    { "job.new", new_cb, NULL },
    { "job.state.priority", priority_cb, NULL },
    { "job.priority.get", priority_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "job.state.depend", depend_cb, NULL },
    { "job.update", job_updated, NULL},
    { "job.state.run", run_cb, NULL},
    { "plugin.query", query_cb, NULL},
    { "job.update.attributes.system.queue", update_queue_cb, NULL },
    { 0 },
};


extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    if (flux_plugin_register (p, "mf_priority", tab) < 0
        || flux_jobtap_service_register (p, "rec_update", rec_update_cb, p)
        || flux_jobtap_service_register (p, "reprioritize", reprior_cb, p)
        || flux_jobtap_service_register (p, "rec_q_update", rec_q_cb, p) < 0)
        return -1;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
