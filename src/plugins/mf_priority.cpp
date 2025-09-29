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
#include <cstdint>

// custom Association class file
#include "accounting.hpp"
// custom job resource counting file
#include "jj.hpp"
// custom Job class file
#include "job.hpp"

// the plugin does not know about the association who submitted a job and will
// assign default values to the association until it receives information from
// flux-accounting
#define BANK_INFO_MISSING 999

// default weights for each factor in the priority calculation for a job
#define DEFAULT_FSHARE_WEIGHT 100000
#define DEFAULT_QUEUE_WEIGHT 10000
#define DEFAULT_BANK_WEIGHT 0
#define DEFAULT_URGENCY_WEIGHT 1000

std::map<int, std::map<std::string, Association>> users;
std::map<std::string, Queue> queues;
std::map<std::string, Bank> banks;
std::map<int, std::string> users_def_bank;
std::vector<std::string> projects;
std::map<std::string, int> priority_weights;

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
 *
 * bank: a factor that can further affect the priority of a job based on the
 *     bank the job is submitted under.
 */
int64_t priority_calculation (flux_plugin_t *p, int urgency)
{
    double fshare_factor = 0.0, priority = 0.0, bank_factor = 0.0;
    int queue_factor = 0;
    int fshare_weight, queue_weight, bank_weight, urgency_weight;
    Association *b;

    fshare_weight = priority_weights["fairshare"];
    queue_weight = priority_weights["queue"];
    bank_weight = priority_weights["bank"];
    urgency_weight = priority_weights["urgency"];

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
    bank_factor = b->bank_factor;

    // pack fair-share using memo event; the error check here should not be
    // fatal since we are just posting a memo event that is primarily used by
    // the "flux account jobs" command, which has handling in the case that a
    // fair-share value cannot be retrieved.
    if (flux_jobtap_event_post_pack (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "memo",
                                     "{s:f}",
                                     "fairshare", b->fairshare) < 0)
        flux_log_error (NULL,
                        "priority_calculation (): failed to pack "
                        "association's fair-share in memo event");

    priority = round ((fshare_weight * fshare_factor) +
                      (queue_weight * queue_factor) +
                      (bank_weight * bank_factor) +
                      (urgency_weight * (urgency - FLUX_JOB_URGENCY_DEFAULT)));

    if (priority < 0)
        return FLUX_JOB_PRIORITY_MIN;

    return priority;
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


/*
 * Update the jobspec with the default project the association used to
 * submit their job under.
 */
static int update_jobspec_project (flux_plugin_t *p, int userid, char *bank)
{
    Association *a = get_association (userid, bank, users, users_def_bank);
    if (a == nullptr)
        // association could not be found
        return -1;

    // get association's default project
    std::string project = a->def_project;

    if (!project.empty ()) {
        // post jobspec-update event
        if (flux_jobtap_jobspec_update_pack (p,
                                             "{s:s}",
                                             "attributes.system.project",
                                             project.c_str ()) < 0)
            return -1;
    }

    return 0;
}


/*
 * Create a special Association object for an association's job while the
 * plugin waits for flux-accounting data to be loaded.
 */
static void add_special_association (flux_plugin_t *p, flux_t *h, int userid)
{
    Association *a;

    a = &users[userid]["DNE"];
    users_def_bank[userid] = "DNE";

    a->bank_name = "DNE";
    a->fairshare = 0.1;
    a->max_run_jobs = BANK_INFO_MISSING;
    a->cur_run_jobs = 0;
    a->max_active_jobs = 1000;
    a->cur_active_jobs = 0;
    a->active = 1;
    a->held_jobs = std::vector<Job>();
    a->max_nodes = INT16_MAX;
    a->max_cores = INT16_MAX;

    if (flux_jobtap_job_aux_set (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "mf_priority:bank_info",
                                 a,
                                 NULL) < 0)
        flux_log_error (h, "flux_jobtap_job_aux_set");
}


/*
 * Using the jobspec from a job, increment the cur_nodes and cur_cores counts
 * for an association.
 */
static int increment_resources (Association *b,
                                const std::string &queue,
                                json_t *jobspec)
{
    struct jj_counts counts;

    if (jj_get_counts_json (jobspec, &counts) < 0)
        return -1;

    if ((counts.nslots * counts.slot_size) > 0 && counts.nnodes == 0)
        // the job only specified cores; set nnodes == 1
        counts.nnodes = 1;

    b->cur_nodes = b->cur_nodes + counts.nnodes;
    b->cur_cores = b->cur_cores + (counts.nslots * counts.slot_size);

    // increment cur_nodes for queue
    if (!queue.empty ())
        b->queue_usage[queue].cur_nodes = b->queue_usage[queue].cur_nodes +
                                          counts.nnodes;

    return 0;
}


/*
 * Using the jobspec from a job, decrement the cur_nodes and cur_cores counts
 * for an association.
 */
static int decrement_resources (Association *b,
                                const std::string &queue,
                                json_t *jobspec)
{
    struct jj_counts counts;

    if (jj_get_counts_json (jobspec, &counts) < 0)
        return -1;

    if ((counts.nslots * counts.slot_size) > 0 && counts.nnodes == 0)
        // the job only specified cores; set nnodes == 1
        counts.nnodes = 1;

    b->cur_nodes = b->cur_nodes - counts.nnodes;
    b->cur_cores = b->cur_cores - (counts.nslots * counts.slot_size);

    // decrement cur_nodes for queue
    if (!queue.empty ())
        b->queue_usage[queue].cur_nodes = b->queue_usage[queue].cur_nodes -
                                          counts.nnodes;

    return 0;
}


/*
 * Loop through an association's held_jobs vector and see if each job satisfies
 * all requirements to be released by the plugin. Check each flux-accounting
 * limit individually to 1) ensure that the association is under the particular
 * limit, and 2) the job currently contains a dependency related to that
 * particular limit.
 *
 * If by the end of these limit checks, the Job object contains no
 * dependencies, remove the Job from the association's list of held jobs and
 * move onto the next job. If it contains at least one dependency, move the
 * iterator to the next job and check to see if it satisfies all requirements
 * to be released. Continue to loop until we've checked every held job for the
 * association.
 */
static int check_and_release_held_jobs (flux_plugin_t *p, Association *b)
{
    std::string dependency;
    flux_jobid_t held_job_id;
    // the Association has at least one held Job; begin looping through
    // held Jobs and see if they satisfy the requirements to be released
    auto it = b->held_jobs.begin ();
    while (it != b->held_jobs.end ()) {
        // grab held Job object
        Job &held_job = *it;

        // is the association under the max running jobs limit for the
        // queue the held job is submitted under?
        if (b->under_queue_max_run_jobs (held_job.queue, queues) &&
            held_job.contains_dep (D_QUEUE_MRJ)) {
            if (flux_jobtap_dependency_remove (p,
                                               held_job.id,
                                               D_QUEUE_MRJ) < 0) {
                dependency = D_QUEUE_MRJ;
                held_job_id = held_job.id;
                goto error;
            }
            held_job.remove_dep (D_QUEUE_MRJ);
        }
        // is the association under the max nodes limit for the queue the
        // held job is submitted under?
        if (b->under_queue_max_resources (held_job, held_job.queue, queues) &&
            held_job.contains_dep (D_QUEUE_MRES)) {
            if (flux_jobtap_dependency_remove (p,
                                               held_job.id,
                                               D_QUEUE_MRES) < 0) {
                dependency = D_QUEUE_MRES;
                held_job_id = held_job.id;
                goto error;
            }
            held_job.remove_dep (D_QUEUE_MRES);
        }
        // is association under their overall max running jobs limit?
        if (b->under_max_run_jobs () && held_job.contains_dep (D_ASSOC_MRJ)) {
            if (flux_jobtap_dependency_remove (p,
                                               held_job.id,
                                               D_ASSOC_MRJ) < 0) {
                dependency = D_ASSOC_MRJ;
                goto error;
            }
            held_job.remove_dep (D_ASSOC_MRJ);
        }
        // will association stay under or at their overall max resources limit
        // by releasing this job?
        if (b->under_max_resources (held_job) &&
            held_job.contains_dep (D_ASSOC_MRES)) {
            if (flux_jobtap_dependency_remove (p,
                                               held_job.id,
                                               D_ASSOC_MRES) < 0) {
                dependency = D_ASSOC_MRES;
                held_job_id = held_job.id;
                goto error;
            }
            held_job.remove_dep (D_ASSOC_MRES);
        }

        if (held_job.deps.empty ())
            // the Job no longer has any flux-accounting dependencies on
            // it; remove it from the Association's vector of held jobs
            // (erase () will return the next valid iterator)
            it = b->held_jobs.erase (it);
        else
            // the job did not meet all requirements to be released;
            // move onto the next Job
            ++it;
    }
error:
    flux_jobtap_raise_exception (p,
                                 held_job_id,
                                 "mf_priority",
                                 0,
                                 "check_and_release_held_jobs: failed to "
                                 "remove %s dependency from job %ju",
                                 dependency.c_str (),
                                 held_job_id);
    return -1;
}


/*
 * Take a vector of strings and join them into just one string with a custom
 * delimiter.
 */
std::string join_strings (const std::vector<std::string> &vec,
                          const std::string &delimiter)
{
    std::string result;
    bool first = true;
    for (const std::string &s : vec) {
        if (!first)
            result += delimiter;
        result += s;
        first = false;
    }
    return result;
}


/******************************************************************************
 *                                                                            *
 *                               Callbacks                                    *
 *                                                                            *
 *****************************************************************************/

/*
 * Get config information about the various priority factor weights
 * and assign them in the priority_weights map.
 */
static void rec_factor_cb (flux_t *h,
                           flux_msg_handler_t *mh,
                           const flux_msg_t *msg,
                           void *arg)
{
    char *factor = NULL;
    long int weight = 0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;
    size_t index;
    json_t *el;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid bank info payload");
        goto error;
    }
    num_data = json_array_size (data);

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0,
                            "{s:s, s:I}",
                            "factor", &factor,
                            "weight", &weight) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        if (factor != NULL)
            priority_weights[factor] = weight;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


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

    json_t *queue_data = convert_queues_to_json (queues);

    if (!queue_data)
        return -1;

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "queues",
                              queue_data) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "mf_priority: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (queue_data);

    json_t *project_data = convert_projects_to_json (projects);

    if (!project_data)
        return -1;

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O}",
                              "projects",
                              project_data) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "mf_priority: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (project_data);

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
    char *bank, *def_bank, *assoc_queues, *assoc_projects, *def_project = NULL;
    int uid, max_running_jobs, max_active_jobs, max_nodes, max_cores = 0;
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

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid bulk_update payload");
        goto error;
    }
    num_data = json_array_size (data);

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0,
                            "{s:i, s:s, s:s, s:F, s:i,"
                            " s:i, s:s, s:i, s:s, s:s, s:i, s:i}",
                            "userid", &uid,
                            "bank", &bank,
                            "def_bank", &def_bank,
                            "fairshare", &fshare,
                            "max_running_jobs", &max_running_jobs,
                            "max_active_jobs", &max_active_jobs,
                            "queues", &assoc_queues,
                            "active", &active,
                            "projects", &assoc_projects,
                            "def_project", &def_project,
                            "max_nodes", &max_nodes,
                            "max_cores", &max_cores) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        Association *b;
        b = &users[uid][bank];

        b->bank_name = bank;
        b->fairshare = fshare;
        b->max_run_jobs = max_running_jobs;
        b->max_active_jobs = max_active_jobs;
        b->active = active;
        b->def_project = def_project;
        b->max_nodes = max_nodes;
        b->max_cores = max_cores;

        // split queues comma-delimited string and add it to b->queues vector
        b->queues.clear ();
        if (has_text (assoc_queues))
            split_string_and_push_back (assoc_queues, b->queues);
        // do the same thing for the association's projects
        b->projects.clear ();
        if (has_text (assoc_projects))
            split_string_and_push_back (assoc_projects, b->projects);

        users_def_bank[uid] = def_bank;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
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
    int max_running_jobs, max_nodes_per_assoc = 0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

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
                            "{s:s, s:i, s:i, s:i, s:i, s:i, s:i}",
                            "queue", &queue,
                            "min_nodes_per_job", &min_nodes_per_job,
                            "max_nodes_per_job", &max_nodes_per_job,
                            "max_time_per_job", &max_time_per_job,
                            "priority", &priority,
                            "max_running_jobs", &max_running_jobs,
                            "max_nodes_per_assoc", &max_nodes_per_assoc) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        Queue *q;
        q = &queues[queue];

        q->name = queue;
        q->min_nodes_per_job = min_nodes_per_job;
        q->max_nodes_per_job = max_nodes_per_job;
        q->max_time_per_job = max_time_per_job;
        q->priority = priority;
        q->max_running_jobs = max_running_jobs;
        q->max_nodes_per_assoc = max_nodes_per_assoc;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


/*
 * Unpack a payload from an external bulk update service and place it in the
 * "projects" vector.
 */
static void rec_proj_cb (flux_t *h,
                         flux_msg_handler_t *mh,
                         const flux_msg_t *msg,
                         void *arg)
{
    char *project = NULL;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;
    size_t index;
    json_t *el;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid project info payload");
        goto error;
    }
    num_data = json_array_size (data);

    // clear the projects vector
    projects.clear ();

    json_array_foreach (data, index, el) {
        if (json_unpack_ex (el, &error, 0, "{s:s}", "project", &project) < 0) {
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);
            goto error;
        }
        projects.push_back (project);
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");

    return;
error:
    flux_respond_error (h, msg, errno, flux_msg_last_error (msg));
}


/*
 * Unpack a payload from an external bulk update service and place it in the
 * "banks" map.
 */
static void rec_bank_cb (flux_t *h,
                         flux_msg_handler_t *mh,
                         const flux_msg_t *msg,
                         void *arg)
{
    char *bank_name = NULL;
    double priority = 0.0;
    json_t *data, *jtemp = NULL;
    json_error_t error;
    int num_data = 0;
    size_t index;
    json_t *el;

    if (flux_request_unpack (msg, NULL, "{s:o}", "data", &data) < 0) {
        flux_log_error (h, "failed to unpack custom_priority.trigger msg");
        goto error;
    }

    if (!data || !json_is_array (data)) {
        flux_log (h, LOG_ERR, "mf_priority: invalid bank info payload");
        goto error;
    }
    num_data = json_array_size (data);

    // clear the banks map
    banks.clear ();

    for (int i = 0; i < num_data; i++) {
        json_t *el = json_array_get(data, i);

        if (json_unpack_ex (el, &error, 0,
                            "{s:s, s:F}",
                            "bank", &bank_name,
                            "priority", &priority) < 0)
            flux_log (h, LOG_ERR, "mf_priority unpack: %s", error.text);

        Bank *b;
        b = &banks[bank_name];

        b->name = bank_name;
        b->priority = priority;
    }

    if (flux_respond (h, msg, NULL) < 0)
        flux_log_error (h, "flux_respond");
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

    // iterate through map that stores associations and held job IDs; check to
    // see if any previously-held jobs can now be released with the update
    for (auto &entry: users) {
        auto &banks = entry.second;

        for (auto &bank_entry : banks) {
            if (check_and_release_held_jobs (p, &bank_entry.second) < 0) {
                flux_log_error (h,
                                "rerior_cb: error checking and releasing "
                                "held jobs for user(s)");
            }
        }
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
    char *queue = NULL;
    const char *project = NULL;
    int64_t priority;
    Association *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:i, s{s{s{s?s, s?s, s?s}}}}",
                                "urgency", &urgency,
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue,
                                "project", &project) < 0) {
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

    if (b == nullptr || b->max_run_jobs == BANK_INFO_MISSING) {
        /*
         * The flux-accounting information associated with this job could not
         * be found by the time this job got to job.state.priority. This could
         * be due to Flux being restarted and pending jobs having their aux
         * items reset or the plugin being reloaded and jobs being "re-seen"
         * (see Flux RFC 21). Attempt to look up the association again and
         * attach its information to the job with aux_set.
         */
        Association *assoc = get_association (userid,
                                              bank,
                                              users,
                                              users_def_bank);
        if (assoc == nullptr) {
            if (check_map_for_dne_only (users, users_def_bank) == true)
                // the plugin is still waiting on flux-accounting data to be
                // loaded in; keep the job in PRIORITY
                return flux_jobtap_priority_unavail (p, args);

            // association no longer exists in internal map
            flux_jobtap_raise_exception (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority",
                                         0,
                                         "cannot find user/bank or "
                                         "user/default bank entry for uid: %i",
                                         userid);
            return -1;
        } else {
            if (assoc->bank_name == "DNE")
                // the association still does not have a valid entry in the
                // users map, so keep it in PRIORITY
                return flux_jobtap_priority_unavail (p, args);

            // fetch priority of the associated queue
            assoc->queue_factor = get_queue_info (queue,
                                                  assoc->queues,
                                                  queues);
            if (assoc->queue_factor == INVALID_QUEUE)
                // the queue the association specified is invalid
                return -1;

            // the bank this job was submitted under was unknown when the job
            // was first accepted, so the active jobs count for the association
            // must be incremented
            assoc->cur_active_jobs++;

            // update this job with the now-found association's information
            if (flux_jobtap_job_aux_set (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority:bank_info",
                                         assoc,
                                         NULL) < 0)
                flux_log_error (h, "flux_jobtap_job_aux_set");

            // now that we know the association information related to this
            // job, we need to update the jobspec with the default bank used
            // to submit this job under
            if (update_jobspec_bank (p, userid) < 0) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "job.state.priority: failed to "
                                             "update jobspec with bank name");
                return -1;
            }

            if (project == NULL) {
                // we also need to update the jobspec with the default project
                // used to submit this job under
                if (update_jobspec_project (p, userid, bank) < 0) {
                    flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                                "mf_priority", 0,
                                                "job.state.priority: failed "
                                                "to update jobspec with "
                                                "project name");
                    return -1;
                }
            }
        }
    }

    priority = priority_calculation (p, urgency);

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
    const char *project = NULL;
    flux_job_state_t state;
    int max_run_jobs, cur_active_jobs, max_active_jobs, queue_factor = 0;
    double fairshare = 0.0;
    bool only_dne_data;
    Association *a;
    json_t *jobspec = NULL;
    Job job;
    std::string queue_str;

    // unpack the attributes of the user/bank's submitted job when it
    // enters job.validate and place them into their respective variables
    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:i, s{s{s{s?s, s?s, s?s}}}, s:o}",
                                "userid", &userid,
                                "state", &state,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue,
                                "project", &project,
                                "jobspec", &jobspec) < 0) {
        return flux_jobtap_reject_job (p, args, "unable to unpack bank arg");
    }

    // perform a lookup in the users map of the unpacked user/bank
    a = get_association (userid, bank, users, users_def_bank);

    if (a == nullptr) {
        // the association could not be found in the plugin's internal map,
        // so perform a check to see if the map has any loaded
        // flux-accounting data before rejecting the job
        bool only_dne_data = check_map_for_dne_only (users, users_def_bank);

        if (users.empty () || only_dne_data) {
            add_special_association (p, h, userid);
            return 0;
        } else {
            return flux_jobtap_reject_job (p,
                                           args,
                                           "cannot find user/bank or "
                                           "user/default bank entry "
                                           "for uid: %i",
                                           userid);
        }
    }

    if (a->active == 0)
        // the association entry was disabled; reject the job
        return flux_jobtap_reject_job (p, args, "user/bank entry has been "
                                       "disabled from flux-accounting DB");

    if (get_queue_info (queue, a->queues, queues) == INVALID_QUEUE) {
        // the association specified a queue that they do not belong to; reject
        // the job and return which queues they belong to
        std::string valid_queues = join_strings (a->queues, ",");
        return flux_jobtap_reject_job (p,
                                       args,
                                       MSG_INVALID_QUEUE,
                                       queue,
                                       valid_queues.c_str ());
    }

    if (project != NULL) {
        // a project was specified on job submission; validate it
        if (get_project_info (project, a->projects, projects) < 0) {
            // the association specified a project that they do not belong to
            // or that flux-accounting does not know about; reject the job
            // and return which projects they belong to
            std::string valid_projects = join_strings (a->projects, ",");
            return flux_jobtap_reject_job (p,
                                           args,
                                           MSG_INVALID_PROJECT,
                                           project,
                                           valid_projects.c_str ());
        }
    }

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

    if (jobspec == NULL) {
        flux_jobtap_reject_job (p,
                                args,
                                "failed to unpack jobspec");
    } else {
        // if a queue was not unpacked, just set it to ""
        queue_str = queue ? queue : "";
        // count resources requested for the job
        if (job.count_resources (jobspec) < 0) {
            return flux_jobtap_reject_job (p,
                                           args,
                                           "unable to count resources for "
                                           "job");
        }
        // look up queue in queues map to see if it has a defined
        // max_nodes_per_association limit
        if (queues.find (queue_str) != queues.end ()) {
            int queue_max_nodes = queues[queue_str].max_nodes_per_assoc;
            if (job.nnodes > queue_max_nodes) {
                // the job size is greater than the max nodes per-association limit
                // configured for this queue; reject the job
                return flux_jobtap_reject_job (p,
                                               args,
                                               MSG_QUEUE_MRES,
                                               job.nnodes,
                                               queue_max_nodes);
            }
        }
        if ((job.nnodes > a->max_nodes) || (job.ncores > a->max_cores)) {
            // the job size is greater than the max resources limits (max nodes
            // OR max cores) configured for this association; reject the job
            return flux_jobtap_reject_job (p,
                                           args,
                                           MSG_ASSOC_MRES,
                                           job.nnodes,
                                           job.ncores,
                                           a->max_nodes,
                                           a->max_cores);
        }
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
    const char *project = NULL;
    int max_run_jobs, cur_active_jobs, max_active_jobs = 0;
    Association *b;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s, s?s, s?s}}}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system",
                                "bank", &bank, "queue", &queue,
                                "project", &project) < 0) {
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
            add_special_association (p, h, userid);
            return 0;
        }

        if (bank == NULL) {
            // this job is meant to run under the association's default bank;
            // as a result, update the jobspec with their default bank name
            if (update_jobspec_bank (p, userid) < 0) {
                flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                             "mf_priority", 0,
                                             "job.new: failed to update "
                                             "jobspec with bank name");
                return -1;
            }
        }
    }

    // assign priority associated with validated queue
    b->queue_factor = get_queue_info (queue, b->queues, queues);
    // assign priority associated with validated bank
    b->bank_factor = get_bank_priority (b->bank_name.c_str (), banks);

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

    if (project == NULL) {
        // this job is meant to run under a default project, so update
        // the jobspec with the project name
        if (update_jobspec_project (p, userid, bank) < 0) {
            flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority", 0,
                                         "job.new: failed to update jobspec "
                                         "with project name");
            return -1;
        }
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
    char *queue = NULL;
    std::string dependency;
    json_t *jobspec = NULL;
    Job job;
    std::string queue_str;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:I, s:o, s{s{s{s?s}}}}",
                                "userid", &userid, "id", &id,
                                "jobspec", &jobspec,
                                "jobspec", "attributes", "system",
                                "queue", &queue) < 0) {
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

    if (jobspec == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.state.depend: failed to unpack " \
                                     "jobspec");
        return -1;
    } else {
        // if a queue cannot be found, just set it to ""
        queue_str = queue ? queue : "";
        // count resources requested for the job
        if (job.count_resources (jobspec) < 0) {
            flux_jobtap_raise_exception (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority",
                                         0,
                                         "job.state.depend: unable to count " \
                                         "resources for job");
            return -1;
        }
        // look up the association's current number of running jobs in this
        // queue; if it cannot be found in the map, an entry in the Association
        // object will be initialized with a current running jobs count of 0
        if (!b->under_queue_max_run_jobs (queue_str, queues)) {
            // association is already at their max number of running jobs
            // in this queue; add a dependency
            if (flux_jobtap_dependency_add (p, id, D_QUEUE_MRJ) < 0)
                goto error;
            job.add_dep (D_QUEUE_MRJ);
        }
        if (!b->under_queue_max_resources (job, queue_str, queues)) {
            // association is already at their max nodes limit across their
            // running jobs in this queue; add a dependency
            if (flux_jobtap_dependency_add (p, id, D_QUEUE_MRES) < 0)
                goto error;
            job.add_dep (D_QUEUE_MRES);
        }
        if (!b->under_max_run_jobs ()) {
            // association is already at their max running jobs count; add a
            // dependency to hold the job until an already running one finishes
            if (flux_jobtap_dependency_add (p, id, D_ASSOC_MRJ) < 0)
                goto error;
            job.add_dep (D_ASSOC_MRJ);
        }
        if (!b->under_max_resources (job)) {
            // association is already at their max resources limit or would be
            // over their max resources limit with this job; add a dependency
            if (flux_jobtap_dependency_add (p, id, D_ASSOC_MRES) < 0) {
                dependency = D_ASSOC_MRES;
                goto error;
            }
            job.add_dep (D_ASSOC_MRES);
        }
        if (job.deps.size () > 0) {
            // Job has at least one dependency; store it in Association object
            job.id = id;
            job.queue = queue_str;
            b->held_jobs.emplace_back (job);
        }
    }

    return 0;
error:
    flux_jobtap_raise_exception (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "mf_priority",
                                 0,
                                 "job.state.depend: failed to add %s "
                                 "dependency to job",
                                 dependency.c_str ());
    return -1;
}


static int run_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid;
    Association *b;
    json_t *jobspec = NULL;
    char *queue = NULL;
    std::string queue_str;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:o, s{s{s{s?s}}}}",
                                "jobspec", &jobspec,
                                "jobspec", "attributes", "system",
                                "queue", &queue) < 0) {
        flux_log (h,
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

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

    if (queue != NULL) {
        // a queue was passed-in; increment counter of the number of
        // queue-specific running jobs for this association
        b->queue_usage[std::string (queue)].cur_run_jobs++;
        queue_str = queue;
    }

    // increment the user's current running jobs count
    b->cur_run_jobs++;
    if (jobspec == NULL) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority",
                                     0,
                                     "job.state.run: failed to unpack " \
                                     "jobspec");
        return -1;
    } else {
        if (increment_resources (b, queue_str, jobspec) < 0) {
            flux_jobtap_raise_exception (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority",
                                         0,
                                         "job.state.run: failed to increment "
                                         "resource count");
            return -1;
        }
    }

    return 0;
}


/*
 *  Apply an update on a job with regard to its queue or associated bank once
 *  it has been validated.
 */
static int job_updated (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    char *bank = NULL;
    char *updated_queue = NULL;
    char *updated_bank = NULL;
    Association *a;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s{s{s{s?s}}}, s:{s?s, s?s}}",
                                "userid", &userid,
                                "jobspec", "attributes", "system", "bank",
                                &bank,
                                "updates",
                                  "attributes.system.queue", &updated_queue,
                                  "attributes.system.bank", &updated_bank) < 0)
        return flux_jobtap_error (p, args, "unable to unpack plugin args");

    // grab Association object from job
    a = static_cast<Association *> (flux_jobtap_job_aux_get (
                                                    p,
                                                    FLUX_JOBTAP_CURRENT_JOB,
                                                    "mf_priority:bank_info"));

    if (a == NULL) {
        flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB, "mf_priority",
                                     0, "job.update: bank info is missing");

        return -1;
    }

    if (updated_bank != NULL && a->bank_name != std::string (updated_bank)) {
        // the bank for the user has been updated, so we need to update
        // the Association object for this job

        // get attributes of new bank
        Association *a_new = get_association (userid,
                                              updated_bank,
                                              users,
                                              users_def_bank);
        if (a_new == nullptr) {
            flux_jobtap_raise_exception (p, FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority", 0,
                                         "job.update: cannot find user/bank "
                                         "or user/default bank entry for "
                                         "uid: %i", userid);

            return -1;
        }

        // update the active jobs count of the old bank
        a->cur_active_jobs--;
        // assign the new Association object to the original Association object
        a = a_new;
        // update the active jobs count of the updated bank
        a->cur_active_jobs++;

        // assign priority associated with validated bank
        a->bank_factor = get_bank_priority (a->bank_name.c_str (), banks);

        // re-pack the updated Association object to the job
        if (flux_jobtap_job_aux_set (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority:bank_info",
                                     a,
                                     NULL) < 0)
            flux_log_error (h, "flux_jobtap_job_aux_set");
    }

    if (updated_queue != NULL)
        // the queue for the job has been updated, so fetch the priority
        // associated with this queue and assign it to the Association object
        // associated with the job
        a->queue_factor = get_queue_info (updated_queue, a->queues, queues);

    return 0;
}


/*
 *  Check for an updated queue and validate it for an association; if the
 *  association does not have access to the queue they are trying to update
 *  their job for, reject the update and keep the job in its current queue.
 */
static int update_queue_cb (flux_plugin_t *p,
                            const char *topic,
                            flux_plugin_arg_t *args,
                            void *data)
{
    int userid;
    char *bank = NULL;
    char *updated_queue = NULL;
    Association *a;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:s, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "value", &updated_queue,
                                "jobspec", "attributes", "system", "bank",
                                &bank) < 0)
        return flux_jobtap_error (p, args, "unable to unpack plugin args");

    // look up association
    a = get_association (userid, bank, users, users_def_bank);

    if (a == nullptr)
        return flux_jobtap_reject_job (p,
                                       args,
                                       "cannot find user/bank or "
                                       "user/default bank entry "
                                       "for uid: %i", userid);

    // validate the updated queue and make sure the user/bank has access to it;
    if (get_queue_info (updated_queue, a->queues, queues) == INVALID_QUEUE)
        // user/bank does not have access to this queue; reject the update
        return flux_jobtap_error (p,
                                  args,
                                  "mf_priority: queue not valid for user: %s",
                                  updated_queue);

    return 0;
}


/*
 *  Check for an updated bank and validate it for a user/bank; if the
 *  user/bank does not have access to the bank they are trying to update
 *  their job for, reject the update and keep the job under its current bank.
 *
 *  Also check the active jobs and running jobs limits for the new bank; if the
 *  new bank is currently at its max active jobs or max running jobs limit,
 *  reject the update and keep the job under its current bank.
 */
static int update_bank_cb (flux_plugin_t *p,
                           const char *topic,
                           flux_plugin_arg_t *args,
                           void *data)
{
    int userid;
    char *bank = NULL;
    Association *a;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:s}",
                                "userid", &userid,
                                "value", &bank) < 0) {
        return flux_jobtap_error (p, args, "unable to unpack bank arg");
    }

    // look up association
    a = get_association (userid, bank, users, users_def_bank);
    if (a == nullptr) {
        // the association could not be found in the plugin's internal map,
        // so perform a check to see if the map has any loaded flux-accounting
        // data before rejecting the update
        bool only_dne_data = check_map_for_dne_only (users, users_def_bank);

        if (users.empty () || only_dne_data) {
            return flux_jobtap_error (p,
                                      args,
                                      "update_bank: plugin still waiting on "
                                      "flux-accounting data");
        } else {
            return flux_jobtap_error (p,
                                      args,
                                      "update_bank: cannot find "
                                      "flux-accounting entry for uid/bank: "
                                      "%i/%s",
                                      userid, bank);
        }
    }

    if (a->max_active_jobs > 0 && a->cur_active_jobs >= a->max_active_jobs)
        // new bank is already at its max active jobs limit; reject update
        return flux_jobtap_error (p,
                                  args,
                                  "new bank is already at max-active-jobs "
                                  "limit");

    if (a->max_run_jobs > 0 && a->cur_run_jobs == a->max_run_jobs)
        // jobs are held in DEPEND state when an association is at their max
        // running jobs limit and there isn't a way to bring a job back to
        // DEPEND, so just reject the update
        return flux_jobtap_error (p,
                                  args,
                                  "updating to bank %s while it is already at "
                                  "max-run-jobs limit is not allowed; try "
                                  "again later",
                                  bank);

    return 0;
}


static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    Association *b;
    json_t *jobspec = NULL;
    char *queue = NULL;
    std::string queue_str;

    flux_t *h = flux_jobtap_get_flux (p);
    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:o, s{s{s{s?s}}}}",
                                "userid", &userid,
                                "jobspec", &jobspec,
                                "jobspec", "attributes", "system",
                                "queue", &queue) < 0) {
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
    // if a queue cannot be found, just set it to ""
    queue_str = queue ? queue : "";

    b->cur_active_jobs--;
    // nothing more to do if this job was never running
    if (!flux_jobtap_job_event_posted (p, FLUX_JOBTAP_CURRENT_JOB, "alloc"))
        return 0;

    // this job was running, so decrement the current running jobs count
    // and the resources count and look to see if any held jobs can be released
    b->cur_run_jobs--;
    if (jobspec == NULL) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "mf_priority",
                                     0,
                                     "job.state.inactive: failed to " \
                                     "unpack jobspec");
        return -1;
    } else {
        if (decrement_resources (b, queue_str, jobspec) < 0) {
            flux_jobtap_raise_exception (p,
                                         FLUX_JOBTAP_CURRENT_JOB,
                                         "mf_priority",
                                         0,
                                         "job.state.inactive: failed to " \
                                         "decrement resource count");
            return -1;
        }
    }

    if (!queue_str.empty ()) {
        if (b->queue_usage[queue_str].cur_run_jobs > 0)
            // decrement num of running jobs the association has in queue
            b->queue_usage[queue_str].cur_run_jobs--;
    }

    if (!b->held_jobs.empty ()) {
        // the Association has at least one held Job; begin looping through
        // held Jobs and see if they satisfy the requirements to be released
        if (check_and_release_held_jobs (p, b) < 0)
            goto error;
    }

    return 0;
error:
    flux_jobtap_raise_exception (p,
                                 FLUX_JOBTAP_CURRENT_JOB,
                                 "mf_priority",
                                 0,
                                 "job.state.inactive: failed to check and "
                                 "release association's held jobs");
    return -1;
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
    { "job.update.attributes.system.bank", update_bank_cb, NULL },
    { 0 },
};


extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    if (flux_plugin_register (p, "mf_priority", tab) < 0
        || flux_jobtap_service_register (p, "rec_update", rec_update_cb, p) < 0
        || flux_jobtap_service_register (p, "reprioritize", reprior_cb, p) < 0
        || flux_jobtap_service_register (p, "rec_q_update", rec_q_cb, p) < 0
        || flux_jobtap_service_register (p, "rec_proj_update", rec_proj_cb, p)
        < 0
        || flux_jobtap_service_register (p, "rec_bank_update", rec_bank_cb, p)
        < 0
        || flux_jobtap_service_register (p, "rec_fac_update", rec_factor_cb, p)
        < 0)
        return -1;

    // initialize the weights of the priority factors with default values
    priority_weights["fairshare"] = DEFAULT_FSHARE_WEIGHT;
    priority_weights["queue"] = DEFAULT_QUEUE_WEIGHT;
    priority_weights["bank"] = DEFAULT_BANK_WEIGHT;
    priority_weights["urgency"] = DEFAULT_URGENCY_WEIGHT;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
