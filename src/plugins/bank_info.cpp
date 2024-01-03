/************************************************************\
 * Copyright 2023 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include "bank_info.hpp"

std::string user_bank_info::to_json () const {
    json_t *u = json_object ();

    json_object_set_new (u, "bank_name", json_string (bank_name.c_str ()));
    json_object_set_new (u, "fairshare", json_real (fairshare));
    json_object_set_new (u, "max_run_jobs", json_integer (max_run_jobs));
    json_object_set_new (u, "cur_run_jobs", json_integer (cur_run_jobs));
    json_object_set_new (u, "max_active_jobs", json_integer (max_active_jobs));
    json_object_set_new (u, "cur_active_jobs", json_integer (cur_active_jobs));

    json_t *held_job_ids = json_array ();
    for (const auto &job_id : held_jobs) {
        json_array_append_new (held_job_ids, json_integer (job_id));
    }
    json_object_set_new(u, "held_jobs", held_job_ids);

    json_t *user_queues = json_array ();
    for (const auto &queue : queues) {
        json_array_append_new (user_queues, json_string (queue.c_str ()));
    }
    json_object_set_new (u, "queues", user_queues);

    json_object_set_new (u, "queue_factor", json_integer (queue_factor));
    json_object_set_new (u, "active", json_integer (active));

    char *json_str = json_dumps(u, JSON_INDENT (4));
    std::string result (json_str);
    free (json_str);
    json_decref (u);

    return result;
}


user_bank_info* get_user_info (int userid, char *bank)
{
    std::map<std::string, user_bank_info>::iterator bank_it;

    auto it = users.find (userid);
    if (it == users.end ())
        return NULL;

    if (bank != NULL) {
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return NULL;
    } else {
        bank = const_cast<char*> (users_def_bank[userid].c_str ());
        bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return NULL;
    }

    return &bank_it->second;
}


json_t* map_to_json ()
{
    json_t *users_map = json_array ();

    // each user_bank in the users map is a pair; the first item is the
    // userid and the second is a list of banks they belong to
    for (const auto& user_bank : users) {
        json_t *u = json_object ();
        json_object_set_new (u, "userid", json_integer (user_bank.first));

        // the user might belong to multiple banks, so we need to iterate
        // through each one
        json_t *banks = json_array ();
        for (const auto& bank : user_bank.second) {
            // bank.second refers to a user_bank_info object
            user_bank_info ub = bank.second;
            json_t *b = json_loads (ub.to_json ().c_str (), 0, nullptr);
            json_array_append_new (banks, b);
        }

        json_object_set_new (u, "banks", banks);
        json_array_append_new (users_map, u);
    }

    return users_map;
}
