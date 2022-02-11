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

#define BANK_INFO_MISSING -9
#define NO_SUCH_QUEUE -5
#define INVALID_QUEUE -6
#define NO_DEFAULT_QUEUE -7

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
};

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


static int get_queue_info (
                      char *queue,
                      std::map<std::string, struct bank_info>::iterator bank_it)
{
    std::map<std::string, struct queue_info>::iterator q_it;

    // make sure that if a queue is passed in, it 1) exists, and 2) is a valid
    // queue for the user to run jobs in
    if (queue != NULL) {
        // check #1) the queue passed in exists in the queues map
        q_it = queues.find (queue);
        if (q_it == queues.end ())
            return NO_SUCH_QUEUE;

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
        // no queue was specified, so use default queue and associated priority
        q_it = queues.find ("default");

        if (q_it == queues.end ())
            return NO_DEFAULT_QUEUE;
        else
            return queues["default"].priority;
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
    if (queue_factor == NO_SUCH_QUEUE) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0,
                                     "%sQueue does not exist: %s",
                                     prefix, queue);
        return -1;
    } else if (queue_factor == INVALID_QUEUE) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "%sQueue not valid for user: %s",
                                     prefix, queue);
        return -1;
    }
    else if (queue_factor == NO_DEFAULT_QUEUE) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority", 0,
                                     "No default queue exists");
        return -1;
    }

    return 0;
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
    char *bank, *def_bank, *queues = NULL;
    int uid, max_running_jobs, max_active_jobs = 0;
    double fshare = 0.0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;
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
                            "{s:i, s:s, s:s, s:F, s:i, s:i, s:s}",
                            "userid", &uid,
                            "bank", &bank,
                            "def_bank", &def_bank,
                            "fairshare", &fshare,
                            "max_running_jobs", &max_running_jobs,
                            "max_active_jobs", &max_active_jobs,
                            "queues", &queues) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        struct bank_info *b;
        b = &users[uid][bank];

        b->fairshare = fshare;
        b->max_run_jobs = max_running_jobs;
        b->max_active_jobs = max_active_jobs;

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
    b->max_active_jobs = 0;
    b->cur_active_jobs = 0;
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

    // fetch priority associated with passed-in queue (or default queue)
    bank_it->second.queue_factor = get_queue_info (queue, bank_it);

    if (bank_it->second.queue_factor == NO_SUCH_QUEUE)
        return flux_jobtap_reject_job (p, args, "Queue does not exist: %s",
                                       queue);
    else if (bank_it->second.queue_factor == INVALID_QUEUE)
        return flux_jobtap_reject_job (p, args, "Queue not valid for user: %s",
                                       queue);
    else if (bank_it->second.queue_factor == NO_DEFAULT_QUEUE)
        return flux_jobtap_reject_job (p, args, "No default queue exists");

    max_run_jobs = bank_it->second.max_run_jobs;
    fairshare = bank_it->second.fairshare;
    cur_active_jobs = bank_it->second.cur_active_jobs;
    max_active_jobs = bank_it->second.max_active_jobs;

    // if a user's fairshare value is 0, that means they shouldn't be able
    // to run jobs on a system
    if (fairshare == 0)
        return flux_jobtap_reject_job (p, args, "user fairshare value is 0");

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

    // if a user's fairshare value is 0, that means they shouldn't be able
    // to run jobs on a system
    if (fairshare == 0)
        return flux_jobtap_reject_job (p, args, "user fairshare value is 0");

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

        if (flux_jobtap_dependency_remove (p, jobid, "max-jobs-limit") < 0)
            flux_jobtap_raise_exception (p, jobid, "mf_priority",
                                         0, "failed to remove job dependency");

        b->held_jobs.erase (b->held_jobs.begin ());
    }

    // delete user's "DNE" entry in internal map (if it exists)
    it = users.find (userid);
    if (it != users.end ())
        it->second.erase ("DNE");

    return 0;
}


static const struct flux_plugin_handler tab[] = {
    { "job.validate", validate_cb, NULL },
    { "job.new", new_cb, NULL },
    { "job.state.priority", priority_cb, NULL },
    { "job.priority.get", priority_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "job.state.depend", depend_cb, NULL },
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
