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
 *
 * Per-user quotas are read from the [accounting.quotas.user] table of the
 * broker configuration. A job that alone requests more of a resource type
 * than its quota allows is rejected at submission. A job that would push
 * its user over a quota when combined with their running jobs is held in
 * DEPEND state with a resource-quota-user dependency until enough of the
 * user's jobs finish for it to fit.
 */

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

#include <algorithm>
#include <map>
#include <string>
#include <vector>

#include "jj.hpp"

// the dependency placed on jobs held by a per-user quota
#define D_USER_QUOTA "resource-quota-user"

// the total amount of each resource type in use by the running jobs of
// each user, keyed by userid and then by resource type name
std::map<int, std::map<std::string, int>> user_resources;

// the maximum amount of each resource type a single user may have in use
// at once, keyed by resource type name; a type not present has no quota
std::map<std::string, int> user_quotas;

// a job held in DEPEND state because it would exceed a per-user quota
struct held_job {
    flux_jobid_t id;
    std::map<std::string, int> counts;
};

// the jobs held by a per-user quota, keyed by userid and ordered by job
// id so that jobs are released in submission order
std::map<int, std::vector<held_job>> held_jobs;

// look up the current usage of a user without inserting an entry
static const std::map<std::string, int> &usage_of (int userid)
{
    static const std::map<std::string, int> empty;
    auto it = user_resources.find (userid);
    return it == user_resources.end () ? empty : it->second;
}

/*
 * Return true if adding request to usage would exceed a per-user quota,
 * setting type to the name of the first resource type over quota.
 */
static bool exceeds_quota (const std::map<std::string, int> &usage,
                           const std::map<std::string, int> &request,
                           std::string &type)
{
    for (const auto &quota : user_quotas) {
        int total = resource_count (usage, quota.first)
                    + resource_count (request, quota.first);
        if (total > quota.second) {
            type = quota.first;
            return true;
        }
    }
    return false;
}

/*
 * Unpack the userid and jobspec for the current job and count the total
 * resources the job requests. Returns 0 on success. Returns -1 on failure
 * with counts.error set to an error message.
 */
static int count_job_resources (flux_plugin_arg_t *args,
                                int &userid,
                                jj_counts &counts)
{
    json_t *jobspec = NULL;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:i, s:o}",
                                "userid", &userid,
                                "jobspec", &jobspec) < 0) {
        counts.error = flux_plugin_arg_strerror (args);
        return -1;
    }
    if (jj_get_counts_json (jobspec, counts) < 0)
        return -1;
    return 0;
}

/*
 * Count the resources of the current job, raising a job exception if the
 * jobspec cannot be counted. Returns 0 on success and -1 on failure.
 */
static int get_job_resources (flux_plugin_t *p,
                              const char *topic,
                              flux_plugin_arg_t *args,
                              int &userid,
                              jj_counts &counts)
{
    if (count_job_resources (args, userid, counts) < 0) {
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

// record a job as held by a per-user quota, keeping the user's held jobs
// ordered by job id
static void hold_job (int userid, flux_jobid_t id, const jj_counts &counts)
{
    auto &jobs = held_jobs[userid];
    auto pos = std::lower_bound (jobs.begin (),
                                 jobs.end (),
                                 id,
                                 [] (const held_job &job, flux_jobid_t id) {
                                     return job.id < id;
                                 });
    if (pos != jobs.end () && pos->id == id)
        return;
    jobs.insert (pos, held_job{id, counts.counts});
}

// forget a held job, e.g. because it was canceled before it ran
static void unhold_job (int userid, flux_jobid_t id)
{
    auto it = held_jobs.find (userid);
    if (it == held_jobs.end ())
        return;
    auto &jobs = it->second;
    jobs.erase (std::remove_if (jobs.begin (),
                                jobs.end (),
                                [id] (const held_job &job) {
                                    return job.id == id;
                                }),
                jobs.end ());
    if (jobs.empty ())
        held_jobs.erase (it);
}

/*
 * Release every held job of a user that now fits under their quotas. Jobs
 * are considered in submission order. Resources of jobs released earlier
 * in the same pass are counted as if in use, since those jobs have not
 * started running yet. Returns 0 on success. Returns -1 and raises an
 * exception on the held job if its dependency cannot be removed.
 */
static int release_held_jobs (flux_plugin_t *p, int userid)
{
    auto it = held_jobs.find (userid);
    if (it == held_jobs.end ())
        return 0;

    std::map<std::string, int> projected = usage_of (userid);
    std::string type;
    auto &jobs = it->second;
    auto job = jobs.begin ();
    while (job != jobs.end ()) {
        if (exceeds_quota (projected, job->counts, type)) {
            ++job;
            continue;
        }
        if (flux_jobtap_dependency_remove (p, job->id, D_USER_QUOTA) < 0) {
            flux_jobtap_raise_exception (p,
                                         job->id,
                                         "resource_quotas",
                                         0,
                                         "failed to remove %s dependency",
                                         D_USER_QUOTA);
            return -1;
        }
        for (const auto &entry : job->counts)
            projected[entry.first] += entry.second;
        job = jobs.erase (job);
    }
    if (jobs.empty ())
        held_jobs.erase (it);

    return 0;
}

// release the held jobs of every user, e.g. after quotas were raised
static int release_all_held_jobs (flux_plugin_t *p)
{
    std::vector<int> userids;
    for (const auto &user : held_jobs)
        userids.push_back (user.first);
    for (int userid : userids) {
        if (release_held_jobs (p, userid) < 0)
            return -1;
    }
    return 0;
}

/*
 * Parse the [accounting.quotas.user] table of the broker configuration
 * into quotas. Returns 0 on success. Returns -1 on failure with error set
 * to an error message.
 */
static int parse_user_quotas (json_t *conf,
                              std::map<std::string, int> &quotas,
                              std::string &error)
{
    json_t *user = NULL;
    const char *type;
    json_t *value;

    if (json_unpack (conf,
                     "{s?{s?{s?o}}}",
                     "accounting",
                     "quotas",
                     "user", &user) < 0) {
        error = "failed to unpack accounting.quotas.user";
        return -1;
    }
    if (user == NULL)
        return 0;
    if (!json_is_object (user)) {
        error = "accounting.quotas.user must be a table";
        return -1;
    }
    json_object_foreach (user, type, value) {
        if (!json_is_integer (value) || json_integer_value (value) < 0) {
            error = std::string ("accounting.quotas.user.") + type
                    + " must be a non-negative integer";
            return -1;
        }
        quotas[type] = json_integer_value (value);
    }
    return 0;
}

/*
 * The broker configuration was loaded or reloaded. Replace the per-user
 * quotas with the ones it defines and release any held jobs that fit
 * under the new quotas.
 */
static int conf_update_cb (flux_plugin_t *p,
                           const char *topic,
                           flux_plugin_arg_t *args,
                           void *data)
{
    json_t *conf = NULL;
    std::map<std::string, int> quotas;
    std::string error;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:o}",
                                "conf", &conf) < 0)
        return flux_jobtap_error (p,
                                  args,
                                  "resource_quotas: failed to unpack conf: %s",
                                  flux_plugin_arg_strerror (args));
    if (parse_user_quotas (conf, quotas, error) < 0)
        return flux_jobtap_error (p, args, "resource_quotas: %s", error.c_str ());

    user_quotas = quotas;

    return release_all_held_jobs (p);
}

/*
 * A job is being submitted. Reject it if it alone requests more of a
 * resource type than the per-user quota allows, since it could never run.
 */
static int validate_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    jj_counts counts;
    std::string type;

    if (count_job_resources (args, userid, counts) < 0)
        return flux_jobtap_reject_job (p,
                                       args,
                                       "failed to count job resources: %s",
                                       counts.error.c_str ());
    if (exceeds_quota ({}, counts.counts, type))
        return flux_jobtap_reject_job (p,
                                       args,
                                       "job requests %d %s but the per-user "
                                       "quota is %d",
                                       counts.get (type),
                                       type.c_str (),
                                       user_quotas[type]);
    return 0;
}

/*
 * A new job was introduced to the plugin. This fires at submission for
 * new jobs and also once for every active job when the plugin is loaded.
 * If the job is already running it is counted here, since its run
 * callback fired before this plugin was loaded.
 *
 * The dependencies of a job are not visible to the plugin, so a job in
 * DEPEND state that has had a dependency added is checked against the
 * quotas again. Running jobs are replayed first (see flux_plugin_init),
 * so usage is complete by then. If the job is over quota it is held
 * again; adding the dependency is a no-op if it is already present. If
 * it fits, the dependency is removed in case usage dropped while the
 * plugin was not loaded; removing a dependency the job does not have
 * fails harmlessly.
 */
static int new_cb (flux_plugin_t *p,
                   const char *topic,
                   flux_plugin_arg_t *args,
                   void *data)
{
    int userid;
    flux_jobid_t id;
    flux_job_state_t state;
    jj_counts counts;
    std::string type;

    if (flux_plugin_arg_unpack (args,
                                FLUX_PLUGIN_ARG_IN,
                                "{s:I, s:i}",
                                "id", &id,
                                "state", &state) < 0) {
        flux_log (flux_jobtap_get_flux (p),
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }

    if (state == FLUX_JOB_STATE_RUN) {
        if (get_job_resources (p, topic, args, userid, counts) < 0)
            return -1;
        add_resources (userid, counts);
    }
    else if (state == FLUX_JOB_STATE_DEPEND
             && flux_jobtap_job_event_posted (p,
                                              FLUX_JOBTAP_CURRENT_JOB,
                                              "dependency-add")) {
        if (get_job_resources (p, topic, args, userid, counts) < 0)
            return -1;
        if (exceeds_quota (usage_of (userid), counts.counts, type)) {
            if (flux_jobtap_dependency_add (p, id, D_USER_QUOTA) < 0) {
                flux_jobtap_raise_exception (p,
                                             FLUX_JOBTAP_CURRENT_JOB,
                                             "resource_quotas",
                                             0,
                                             "%s: failed to add %s dependency",
                                             topic,
                                             D_USER_QUOTA);
                return -1;
            }
            hold_job (userid, id, counts);
        }
        else
            (void) flux_jobtap_dependency_remove (p, id, D_USER_QUOTA);
    }

    return 0;
}

/*
 * A job is in DEPEND state. If its resources combined with those in use
 * by the running jobs of its user would exceed a per-user quota, hold it
 * with a dependency until enough of the user's jobs finish.
 */
static int depend_cb (flux_plugin_t *p,
                      const char *topic,
                      flux_plugin_arg_t *args,
                      void *data)
{
    int userid;
    flux_jobid_t id;
    jj_counts counts;
    std::string type;

    if (flux_plugin_arg_unpack (args, FLUX_PLUGIN_ARG_IN, "{s:I}", "id", &id)
        < 0) {
        flux_log (flux_jobtap_get_flux (p),
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }
    if (get_job_resources (p, topic, args, userid, counts) < 0)
        return -1;

    if (!exceeds_quota (usage_of (userid), counts.counts, type))
        return 0;

    if (flux_jobtap_dependency_add (p, id, D_USER_QUOTA) < 0) {
        flux_jobtap_raise_exception (p,
                                     FLUX_JOBTAP_CURRENT_JOB,
                                     "resource_quotas",
                                     0,
                                     "%s: failed to add %s dependency",
                                     topic,
                                     D_USER_QUOTA);
        return -1;
    }
    hold_job (userid, id, counts);

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
 * totals from the usage of the user that submitted it and release any of
 * the user's held jobs that now fit under their quotas. Entries that reach
 * zero are removed so the tracked state only contains users with running
 * jobs. A job that was canceled while held is simply forgotten.
 */
static int inactive_cb (flux_plugin_t *p,
                        const char *topic,
                        flux_plugin_arg_t *args,
                        void *data)
{
    int userid;
    flux_jobid_t id;
    jj_counts counts;

    if (flux_plugin_arg_unpack (args, FLUX_PLUGIN_ARG_IN, "{s:I}", "id", &id)
        < 0) {
        flux_log (flux_jobtap_get_flux (p),
                  LOG_ERR,
                  "flux_plugin_arg_unpack: %s",
                  flux_plugin_arg_strerror (args));
        return -1;
    }
    if (get_job_resources (p, topic, args, userid, counts) < 0)
        return -1;

    unhold_job (userid, id);

    // a job that never received an allocation was never counted
    if (!flux_jobtap_job_event_posted (p, FLUX_JOBTAP_CURRENT_JOB, "alloc"))
        return 0;

    auto user = user_resources.find (userid);
    if (user != user_resources.end ()) {
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
    }

    return release_held_jobs (p, userid);
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

// build a JSON object of the configured quotas
static json_t *quotas_to_json ()
{
    json_t *user = json_object ();
    if (!user)
        return NULL;
    for (const auto &quota : user_quotas) {
        if (json_object_set_new (user,
                                 quota.first.c_str (),
                                 json_integer (quota.second)) < 0) {
            json_decref (user);
            return NULL;
        }
    }
    return json_pack ("{s:o}", "user", user);
}

// build a JSON object of every user's held job ids
static json_t *held_jobs_to_json ()
{
    json_t *o = json_object ();
    if (!o)
        return NULL;
    for (const auto &user : held_jobs) {
        json_t *ids = json_array ();
        if (!ids)
            goto error;
        for (const auto &job : user.second) {
            if (json_array_append_new (ids, json_integer (job.id)) < 0) {
                json_decref (ids);
                goto error;
            }
        }
        if (json_object_set_new (o,
                                 std::to_string (user.first).c_str (),
                                 ids) < 0) {
            json_decref (ids);
            goto error;
        }
    }
    return o;
error:
    json_decref (o);
    return NULL;
}

/*
 * Report the tracked per-user resource usage, the configured quotas, and
 * the held jobs so they can be inspected with flux jobtap query.
 */
static int query_cb (flux_plugin_t *p,
                     const char *topic,
                     flux_plugin_arg_t *args,
                     void *data)
{
    json_t *usage = user_resources_to_json ();
    json_t *quotas = quotas_to_json ();
    json_t *held = held_jobs_to_json ();

    if (!usage || !quotas || !held) {
        json_decref (usage);
        json_decref (quotas);
        json_decref (held);
        return -1;
    }

    if (flux_plugin_arg_pack (args,
                              FLUX_PLUGIN_ARG_OUT,
                              "{s:O, s:O, s:O}",
                              "user_resources", usage,
                              "quotas", quotas,
                              "held_jobs", held) < 0)
        flux_log_error (flux_jobtap_get_flux (p),
                        "resource_quotas: query_cb: flux_plugin_arg_pack: %s",
                        flux_plugin_arg_strerror (args));

    json_decref (usage);
    json_decref (quotas);
    json_decref (held);

    return 0;
}

static const struct flux_plugin_handler tab[] = {
    { "conf.update", conf_update_cb, NULL },
    { "job.validate", validate_cb, NULL },
    { "job.new", new_cb, NULL },
    { "job.state.depend", depend_cb, NULL },
    { "job.state.run", run_cb, NULL },
    { "job.state.inactive", inactive_cb, NULL },
    { "plugin.query", query_cb, NULL },
    { 0 },
};

extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    // explicitly reset all tracked state so a reload starts clean and is
    // rebuilt from the configuration and the active jobs replayed by the
    // job manager
    user_resources.clear ();
    user_quotas.clear ();
    held_jobs.clear ();

    if (flux_plugin_register (p, "resource_quotas", tab) < 0)
        return -1;

    // replay running jobs before jobs in DEPEND state so that usage is
    // complete when held jobs are checked against the quotas again
    if (flux_jobtap_set_load_sort_order (p, "-state") < 0)
        return -1;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
