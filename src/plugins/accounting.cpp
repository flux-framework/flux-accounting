/************************************************************\
 * Copyright 2024 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include "accounting.hpp"

Association* get_association (int userid,
                              const char *bank,
                              std::map<int, std::map<std::string, Association>>
                                &users,
                              std::map<int, std::string> &users_def_bank)
{
    auto it = users.find (userid);
    if (it == users.end ())
        // user could not be found
        return nullptr;

    std::string b;
    if (bank != NULL)
        b = bank;
    else
        // get the default bank of this user
        b = users_def_bank[userid];

    auto bank_it = it->second.find (b);
    if (bank_it == it->second.end ())
        // user does not have accounting information under the specified bank
        return nullptr;

    return &bank_it->second;
}


json_t* Association::to_json () const
{
    json_t *user_queues = nullptr;
    json_t *user_projects = nullptr;
    json_t *temp = nullptr;
    json_t *queue_usage_json = nullptr;
    json_t *usage_object = nullptr;
    json_t *hj_json = nullptr;
    json_t *job_json = nullptr;
    json_t *deps_array = nullptr;
    json_t *dep_str = nullptr;
    json_t *u = nullptr;

    user_queues = json_array ();
    if (!user_queues)
        goto error;
    for (const auto &queue : queues) {
        if (!(temp = json_string (queue.c_str ()))
            || json_array_append_new (user_queues, temp) < 0)
            goto error;
    }
    // set temp to nullptr here to avoid a double free in case of an error
    temp = nullptr;

    user_projects = json_array ();
    if (!user_projects)
        goto error;
    for (const auto &project : projects) {
        if (!(temp = json_string (project.c_str ()))
            || json_array_append_new (user_projects, temp) < 0)
            goto error;
    }
    temp = nullptr;

    queue_usage_json = json_object ();
    if (!queue_usage_json)
        goto error;
    for (const auto &entry : queue_usage) {
        const QueueUsage &usage = entry.second;
        usage_object = json_pack ("{s:i, s:i}",
                                  "cur_run_jobs", usage.cur_run_jobs,
                                  "cur_nodes", usage.cur_nodes);
        if (!usage_object)
            goto error;

        if (json_object_set_new (queue_usage_json,
                                 entry.first.c_str (),
                                 usage_object) < 0)
            goto error;
    }

    hj_json = json_object ();
    if (!hj_json)
        goto error;

    for (const auto &entry : held_jobs) {
        const Job &job = entry;
        job_json = json_pack ("{s:i, s:i, s:s, s:o}",
                              "nnodes", job.nnodes,
                              "ncores", job.ncores,
                              "queue", job.queue.c_str (),
                              "deps", json_array ());

        if (!job_json)
            goto error;

        deps_array = json_array ();
        if (!deps_array)
            goto error;

        for (const auto &dep : job.deps) {
            dep_str = json_string (dep.c_str ());
            if (!dep_str || json_array_append_new (deps_array, dep_str) < 0)
                goto error;
        }

        if (json_object_set_new (job_json, "deps", deps_array) < 0)
            goto error;

        // use job id (flux_jobid_t) as string key
        char keybuf[32];
        snprintf (keybuf, sizeof(keybuf), "%ld", entry.id);
        if (json_object_set_new (hj_json, keybuf, job_json) < 0)
            goto error;
    }

    // 'o' steals the reference for both held_job_ids and user_queues
    u = json_pack ("{s:s, s:f, s:i, s:i, s:i, s:i"
                   " s:o, s:i, s:o, s:s, s:i, s:i, s:i,"
                   " s:i, s:i, s:o, s:o}",
                   "bank_name", bank_name.c_str (),
                   "fairshare", fairshare,
                   "max_run_jobs", max_run_jobs,
                   "cur_run_jobs", cur_run_jobs,
                   "max_active_jobs", max_active_jobs,
                   "cur_active_jobs", cur_active_jobs,
                   "queues", user_queues,
                   "queue_factor", queue_factor,
                   "projects", user_projects,
                   "def_project", def_project.c_str (),
                   "max_nodes", max_nodes,
                   "max_cores", max_cores,
                   "cur_nodes", cur_nodes,
                   "cur_cores", cur_cores,
                   "active", active,
                   "queue_usage", queue_usage_json,
                   "held_jobs", hj_json);

    if (!u)
        goto error;

    return u;

error:
    json_decref (user_queues);
    json_decref (user_projects);
    json_decref (temp);
    json_decref (queue_usage_json);
    json_decref (usage_object);
    json_decref (hj_json);
    json_decref (deps_array);
    json_decref (job_json);
    json_decref (u);
    return nullptr;
}


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


void split_string_and_push_back (const char *list,
                                 std::vector<std::string> &vec)
{
    std::stringstream s_stream;

    s_stream << list; // create string stream from string

    while (s_stream.good ()) {
        std::string substr;
        getline (s_stream, substr, ','); // get string delimited by comma
        vec.push_back (substr);
    }
}


bool has_text (const char *s) {
    if (!s) return false;
    while (*s && std::isspace (static_cast<unsigned char> (*s))) ++s;
    return *s != '\0';
};


int get_queue_info (char *queue,
                    const std::vector<std::string> &permissible_queues,
                    const std::map<std::string, Queue> &queues)
{
    if (queue != NULL) {
        // check #1) the queue passed in exists in the queues map;
        // if the queue cannot be found, this means that flux-accounting
        // does not know about the queue, and thus should return a default
        // factor
        auto q_it = queues.find (queue);
        if (q_it == queues.end ())
            return UNKNOWN_QUEUE;

        // check #2) the queue passed in is valid for the association
        auto vect_it = std::find (permissible_queues.begin (),
                                  permissible_queues.end (),
                                  queue);
        if (vect_it == permissible_queues.end ())
            // the queue passed in is not valid for the association
            return INVALID_QUEUE;

        try {
            return queues.at (queue).priority;
        } catch (const std::out_of_range &e) {
            return UNKNOWN_QUEUE;
        }
    }

    // no queue was specified, so just use a default queue factor
    return NO_QUEUE_SPECIFIED;
}


bool check_map_for_dne_only (std::map<int, std::map<std::string, Association>>
                               &users,
                             std::map<int, std::string> &users_def_bank)
{
    for (const auto& entry : users) {
        auto it = users_def_bank.find(entry.first);
        if (it != users_def_bank.end() && it->second != "DNE")
            return false;
    }

    return true;
}


int get_project_info (const char *project,
                      std::vector<std::string> &permissible_projects,
                      std::vector<std::string> projects)
{
    auto it = std::find (projects.begin (), projects.end (), project);
    if (it == projects.end ())
        // project is unknown to flux-accounting
        return UNKNOWN_PROJECT;

    it = std::find (permissible_projects.begin (),
                    permissible_projects.end (),
                    project);
    if (it == permissible_projects.end ())
        // association doesn't have access to submit jobs under this project
        return INVALID_PROJECT;

    return 0;
}


bool Association::under_max_run_jobs ()
{
    bool under_assoc_max_run_jobs = cur_run_jobs < max_run_jobs;

    return under_assoc_max_run_jobs;
}


bool Association::under_queue_max_run_jobs (
                                const std::string &queue,
                                std::map<std::string, Queue> queues) {
    bool under_queue_max_run_jobs = queue_usage[queue].cur_run_jobs
                                    < queues[queue].max_running_jobs;

    return under_queue_max_run_jobs;
}


double get_bank_priority (const char *bank,
                          const std::map<std::string, Bank> &banks)
{
    try {
        return banks.at (bank).priority;
    } catch (const std::out_of_range &err) {
        // can't find the bank passed in, so just return 0.0
        return 0.0;
    }
}

bool Association::under_max_resources (const Job &job)
{
    bool under_max_nodes = ((cur_nodes + job.nnodes) <= max_nodes);
    bool under_max_cores = ((cur_cores + job.ncores) <= max_cores);
    bool under_max_resources = (max_nodes > 0 && max_cores > 0) &&
                               (under_max_nodes && under_max_cores);

    return under_max_resources;
}

bool Association::under_queue_max_resources (
                                    const Job &job,
                                    const std::string &queue,
                                    const std::map<std::string, Queue> &queues)
{
    auto qit = queues.find (queue);
    if (qit == queues.end ())
        // queue is unknown to flux-accounting; skip check
        return true;
    const int queue_max_nodes_per_assoc = qit->second.max_nodes_per_assoc;

    // look up current per-queue node usage for the association
    int cur_nodes_in_queue = 0;
    auto uit = queue_usage.find (queue);
    if (uit != queue_usage.end ())
        cur_nodes_in_queue = uit->second.cur_nodes;

    return (cur_nodes_in_queue + job.nnodes) <= queue_max_nodes_per_assoc;
}
