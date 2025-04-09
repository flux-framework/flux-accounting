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
    json_t *held_job_ids = json_array ();
    if (!held_job_ids) {
        return nullptr;
    }
    for (const auto &job_id : held_jobs) {
        json_t *temp;
        if (!(temp = json_integer (job_id))
            || json_array_append_new (held_job_ids, temp) < 0) {
            json_decref (held_job_ids);
            return nullptr;
        }
    }

    json_t *user_queues = json_array ();
    if (!user_queues) {
        json_decref (held_job_ids);
        return nullptr;
    }
    for (const auto &queue : queues) {
        json_t *temp;
        if (!(temp = json_string (queue.c_str ()))
            || json_array_append_new (user_queues, temp) < 0) {
            json_decref (held_job_ids);
            json_decref (user_queues);
            return nullptr;
        }
    }

    json_t *user_projects = json_array ();
    if (!user_projects) {
        json_decref (held_job_ids);
        json_decref (user_queues);
        return nullptr;
    }
    for (const auto &project : projects) {
        json_t *temp;
        if (!(temp = json_string (project.c_str ()))
            || json_array_append_new (user_projects, temp) < 0) {
            json_decref (held_job_ids);
            json_decref (user_queues);
            json_decref (user_projects);
            return nullptr;
        }
    }

    json_t *queue_usage_json = json_object ();
    if (!queue_usage_json) {
        json_decref (held_job_ids);
        json_decref (user_queues);
        json_decref (user_projects);
        return nullptr;
    }
    for (const auto &entry : queue_usage) {
        if (json_object_set_new (queue_usage_json,
                                 entry.first.c_str (),
                                 json_integer (entry.second)) < 0) {
            json_decref (held_job_ids);
            json_decref (user_queues);
            json_decref (user_projects);
            json_decref (queue_usage_json);
            return nullptr;
        }
    }

    // 'o' steals the reference for both held_job_ids and user_queues
    json_t *u = json_pack ("{s:s, s:f, s:i, s:i, s:i, s:i, s:o,"
                           " s:o, s:i, s:o, s:s, s:i, s:i, s:i,"
                           " s:i, s:i, s:o}",
                           "bank_name", bank_name.c_str (),
                           "fairshare", fairshare,
                           "max_run_jobs", max_run_jobs,
                           "cur_run_jobs", cur_run_jobs,
                           "max_active_jobs", max_active_jobs,
                           "cur_active_jobs", cur_active_jobs,
                           "held_jobs", held_job_ids,
                           "queues", user_queues,
                           "queue_factor", queue_factor,
                           "projects", user_projects,
                           "def_project", def_project.c_str (),
                           "max_nodes", max_nodes,
                           "max_cores", max_cores,
                           "cur_nodes", cur_nodes,
                           "cur_cores", cur_cores,
                           "active", active,
                           "queue_usage", queue_usage_json);

    if (!u)
        return nullptr;

    return u;
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
