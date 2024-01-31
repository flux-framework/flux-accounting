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
