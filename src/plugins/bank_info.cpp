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

user_bank_info* get_user_info (int userid,
                               char *bank,
                               std::map<int, std::map<std::string,
                                                      user_bank_info>> &users,
                               std::map<int, std::string> &users_def_bank)
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


bool check_map_for_dne_only (
                std::map<int, std::map<std::string, user_bank_info>> &users,
                std::map<int, std::string> &users_def_bank)
{
    for (const auto& entry : users) {
        auto def_bank_it = users_def_bank.find(entry.first);
        if (def_bank_it != users_def_bank.end() &&
                def_bank_it->second != "DNE")
            return false;
    }

    return true;
}
