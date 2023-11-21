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

int user_bank_lookup (int userid, char *bank)
{
    auto it = users.find (userid);
    if (it == users.end ()) {
        return BANK_USER_NOT_FOUND;
    }

    // make sure user belongs to bank they specified; if no bank was passed in,
    // look up their default bank
    if (bank != NULL) {
        auto bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return BANK_INVALID;
    } else {
        bank = const_cast<char*> (users_def_bank[userid].c_str ());
        auto bank_it = it->second.find (std::string (bank));
        if (bank_it == it->second.end ())
            return BANK_NO_DEFAULT;
    }

    return BANK_SUCCESS;
}


user_bank_info get_user_info (int userid, char *bank)
{
    std::map<std::string, user_bank_info>::iterator bank_it;

    auto it = users.find (userid);

    if (bank != NULL) {
        bank_it = it->second.find (std::string (bank));
    } else {
        bank = const_cast<char*> (users_def_bank[userid].c_str ());
        bank_it = it->second.find (std::string (bank));
    }

    return bank_it->second;
}
