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
#include <sstream>

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

std::map<int, std::map<std::string, struct bank_info>> users;
std::map<std::string, struct queue_info> queues;
std::map<int, std::string> users_def_bank;

struct bank_info {
    double fairshare;
    int max_run_jobs;
    int cur_run_jobs;
    int max_active_jobs;
    int cur_active_jobs;
    std::vector<long int> held_jobs;
    std::vector<std::string> queues;
    int queue_factor;
    int active;
};

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
    struct bank_info *b;

    fshare_weight = 100000;
    queue_weight = 10000;

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
    queue_factor = b->queue_factor;

    priority = round ((fshare_weight * fshare_factor) +
                      (queue_weight * queue_factor) +
                      (urgency - 16));

    if (priority < 0)
        return FLUX_JOB_PRIORITY_MIN;

    return priority;
}


static int get_queue_info (
                      char *queue,
                      std::map<std::string, struct bank_info>::iterator bank_it)
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
        vect_it = std::find (bank_it->second.queues.begin (),
                             bank_it->second.queues.end (), queue);

        if (vect_it == bank_it->second.queues.end ())
            return INVALID_QUEUE;
        else
            // add priority associated with the passed in queue to bank_info
            return queues[queue].priority;
    } else {
        // no queue was specified, so just use a default queue factor
        return NO_QUEUE_SPECIFIED;
    }
}


static void split_string (char *queues, struct bank_info *b)
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


/*
 * Add held job IDs to a JSON array to be added to a bank_info JSON object.
 */
static json_t *add_held_jobs (
                            const std::pair<std::string, struct bank_info> &b)
{
    json_t *held_jobs = NULL;

    // add any held jobs to a JSON array
    if (!(held_jobs = json_array ()))
        goto error;

    for (auto const &j : b.second.held_jobs) {
        json_t *jobid = json_integer (j);

        if (!jobid)
            goto error;

        if (json_array_append_new (held_jobs, jobid) < 0) {
            json_decref (jobid);
            goto error;
        }
    }

    return held_jobs;
error:
    json_decref (held_jobs);
    return NULL;
}


/*
 * Create a JSON object for a bank that a user belongs to.
 */
static json_t *pack_bank_info_object (
                            const std::pair<std::string, struct bank_info> &b)
{
    json_t *bank_info, *held_jobs = NULL;

    held_jobs = add_held_jobs (b);
    if (held_jobs == NULL)
        goto error;

    if (!(bank_info = json_pack ("{s:s, s:f, s:i, s:i, s:i, s:i, s:o, s:i}",
                                 "bank", b.first.c_str (),
                                 "fairshare", b.second.fairshare,
                                 "max_run_jobs", b.second.max_run_jobs,
                                 "cur_run_jobs", b.second.cur_run_jobs,
                                 "max_active_jobs", b.second.max_active_jobs,
                                 "cur_active_jobs", b.second.cur_active_jobs,
                                 "held_jobs", held_jobs,
                                 "active", b.second.active))) {
            goto error;
    }

    return bank_info;
error:
    json_decref (held_jobs);
    return NULL;
}


/*
 * For each bank that a user belongs to, create a JSON object for each bank and
 * add it to the user JSON object.
 */
static json_t *banks_to_json (
                    flux_plugin_t *p,
                    std::pair<int, std::map<std::string, struct bank_info>> &u)
{
    json_t *bank_info, *banks = NULL;

    banks = json_array (); // array of banks that user belongs to
    if (!banks)
        goto error;

    for (auto const &b : u.second) {
        bank_info = pack_bank_info_object (b); // JSON object for one bank
        if (bank_info == NULL)
            goto error;

        if (json_array_append_new (banks, bank_info) < 0) {
            json_decref (bank_info);
            goto error;
        }
    }

    return banks;
error:
    json_decref (banks);
    return NULL;
}


/*
 * Iterate thrpugh each user in users map and create a JSON object for each
 * user.
 */
static json_t *user_to_json (
                    flux_plugin_t *p,
                    std::pair<int, std::map<std::string, struct bank_info>> u)
{
    json_t *user = json_object (); // JSON object for one user
    json_t *userid, *banks = NULL;

    if (!user)
        return NULL;

    userid = json_integer (u.first);
    if (!userid)
        goto error;

    if (json_object_set_new (user, "userid", userid) < 0) {
        json_decref (userid);
        goto error;
    }

    banks = banks_to_json (p, u);
    if (banks == NULL)
        goto error;

    if (json_object_set_new (user, "banks", banks) < 0) {
        json_decref (banks);
        goto error;
    }

    return user;
error:
    json_decref (user);
    return NULL;
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
    json_t *all_users = json_array (); // array of user/bank combos

    if (!all_users)
        return -1;

    for (auto const &u : users) {
        json_t *user = user_to_json (p, u);
        if (user == NULL) {
            json_decref (all_users);
            return -1;
        }

        if (json_array_append_new (all_users, user) < 0) {
            json_decref (user);
            json_decref (all_users);
            return -1;
        }
    }

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "mf_priority_map",
                              all_users) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "mf_priority: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (all_users);

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
    char *bank, *def_bank, *queues = NULL;
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
                            "queues", &queues,
                            "active", &active) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        struct bank_info *b;
        b = &users[uid][bank];

        b->fairshare = fshare;
        b->max_run_jobs = max_running_jobs;
        b->max_active_jobs = max_active_jobs;
        b->active = active;

        // split queues comma-delimited string and add it to b->queues vector
        split_string (queues, b);

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
    int max_run_jobs, cur_run_jobs, max_active_jobs, cur_active_jobs;
    char *bank = NULL;
    char *queue = NULL;
    int64_t priority;
    struct bank_info *b;

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

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "internal error: bank info is missing");

        return -1;
    }

    std::map<int, std::map<std::string, struct bank_info>>::iterator it;
    std::map<std::string, struct bank_info>::iterator bank_it;

    if (b->max_run_jobs == BANK_INFO_MISSING) {
        // try to look up user again
        it = users.find (userid);
        if (it == users.end ()) {
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

            max_active_jobs = bank_it->second.max_active_jobs;
            cur_active_jobs = bank_it->second.cur_active_jobs;
            max_run_jobs = bank_it->second.max_run_jobs;
            cur_run_jobs = bank_it->second.cur_run_jobs;

            if ((max_active_jobs >= 0) && (cur_active_jobs == max_active_jobs)) {
                // user has already hit their max active jobs count,
                // so raise a job exception on this job and return
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "job.state.priority: user has "
                                             "hit max_active_jobs limit");

                return 0;
            }

            // fetch priority associated with passed-in queue (or default queue)
            bank_it->second.queue_factor = get_queue_info (queue, bank_it);
            if (check_queue_factor (p,
                                    bank_it->second.queue_factor,
                                    queue) < 0)
                return -1;

            // if we get here, the bank was unknown when this job was first
            // accepted, and therefore the active and run job counts for this
            // job need to be incremented here
            bank_it->second.cur_active_jobs++;
            bank_it->second.cur_run_jobs++;

            // update current job with user/bank information
            if (flux_jobtap_job_aux_set (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority:bank_info",
                                         &bank_it->second,
                                         NULL) < 0)
                flux_log_error (h, "flux_jobtap_job_aux_set");
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

    b->cur_run_jobs++;

    return 0;
}


static void add_missing_bank_info (flux_plugin_t *p, flux_t *h, int userid)
{
    struct bank_info *b;

    b = &users[userid]["DNE"];
    users_def_bank[userid] = "DNE";

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
    char *queue = NULL;
    int max_run_jobs, cur_active_jobs, max_active_jobs = 0;
    double fairshare = 0.0;

    std::map<int, std::map<std::string, struct bank_info>>::iterator it;
    std::map<std::string, struct bank_info>::iterator bank_it;
    std::map<std::string, struct queue_info>::iterator q_it;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s, s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    // make sure user belongs to flux-accounting DB
    it = users.find (userid);
    if (it == users.end ()) {
        // user does not exist in internal map yet, so create a bank_info
        // struct that signifies it's going to be held in PRIORITY
        add_missing_bank_info (p, h, userid);
        return 0;
    }

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

    // if user/bank entry was disabled, reject job with a message saying the
    // entry has been disabled
    if (bank_it->second.active == 0)
        return flux_jobtap_reject_job (p, args, "user/bank entry has been "
                                       "disabled from flux-accounting DB");

    // fetch priority associated with passed-in queue; if a queue cannot be
    // found, use a default factor for the queue (UNKOWN_QUEUE). If a queue
    // is found but is determined that a user does not have access to submit
    // jobs to it, it can still be rejected.
    bank_it->second.queue_factor = get_queue_info (queue, bank_it);

    if (bank_it->second.queue_factor == INVALID_QUEUE)
        return flux_jobtap_reject_job (p, args, "Queue not valid for user: %s",
                                       queue);

    max_run_jobs = bank_it->second.max_run_jobs;
    fairshare = bank_it->second.fairshare;
    cur_active_jobs = bank_it->second.cur_active_jobs;
    max_active_jobs = bank_it->second.max_active_jobs;

    // if a user/bank has reached their max_active_jobs limit, subsequently
    // submitted jobs will be rejected
    if (max_active_jobs > 0 && cur_active_jobs >= max_active_jobs)
        return flux_jobtap_reject_job (p, args, "user has max active jobs");

    return 0;
}


static int new_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    char *bank = NULL;
    char *queue = NULL;
    int max_run_jobs, cur_active_jobs, max_active_jobs = 0;
    double fairshare = 0.0;
    struct bank_info *b;

    std::map<int, std::map<std::string, struct bank_info>>::iterator it;
    std::map<std::string, struct bank_info>::iterator bank_it;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s, s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    b = static_cast<bank_info *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (b != NULL) {
        max_run_jobs = b->max_run_jobs;
        fairshare = b->fairshare;
        cur_active_jobs = b->cur_active_jobs;
        max_active_jobs = b->max_active_jobs;
    } else {
        // make sure user belongs to flux-accounting DB
        it = users.find (userid);
        if (it == users.end ()) {
            // user does not exist in internal map yet, so create a bank_info
            // struct that signifies it's going to be held in PRIORITY
            add_missing_bank_info (p, h, userid);
            return 0;
        }

        // make sure user belongs to bank they specified; if no bank was passed
        // in, look up their default bank
        if (bank != NULL) {
            bank_it = it->second.find (std::string (bank));
            if (bank_it == it->second.end ()) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "job.new: not a member of %s",
                                             bank);
                return -1;
            }
        } else {
            bank = const_cast<char*> (users_def_bank[userid].c_str ());
            bank_it = it->second.find (std::string (bank));
            if (bank_it == it->second.end ()) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "job.new: user/default bank "
                                             "entry does not exist");
                return -1;
            }
        }

        // fetch priority associated with passed-in queue (or default queue)
        bank_it->second.queue_factor = get_queue_info (queue, bank_it);
        if (check_queue_factor (p,
                                bank_it->second.queue_factor,
                                queue,
                                (char *) "job.new: ") < 0)
            return -1;

        max_run_jobs = bank_it->second.max_run_jobs;
        fairshare = bank_it->second.fairshare;
        cur_active_jobs = bank_it->second.cur_active_jobs;
        max_active_jobs = bank_it->second.max_active_jobs;

        b = &bank_it->second;
    }

    // if a user/bank has reached their max_active_jobs limit, subsequently
    // submitted jobs will be rejected
    if (max_active_jobs > 0 && cur_active_jobs >= max_active_jobs)
        return flux_jobtap_reject_job (p, args, "user has max active jobs");

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
                                 b,
                                 NULL) < 0)
        flux_log_error (h, "flux_jobtap_job_aux_set");

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


static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    struct bank_info *b;
    std::map<int, std::map<std::string, struct bank_info>>::iterator it;
    std::map<std::string, struct bank_info>::iterator bank_it;

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
    b->cur_active_jobs--;

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
    { "plugin.query", query_cb, NULL},
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
