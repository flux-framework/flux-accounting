/************************************************************\
 * Copyright 2020 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include <cerrno>
#include "src/fairness/account/account.hpp"

using namespace Flux::accounting;

account_t::account_t (const std::string &name,
                      bool is_user,  uint64_t shares, uint64_t usage)
{
    m_name = name;
    m_is_user = is_user;
    m_shares = shares;
    m_usage = usage;
}

void account_t::set_name (const std::string &name)
{
    m_name = name;
}

void account_t::set_shares (uint64_t shares)
{
    m_shares = shares;
}

void account_t::set_usage (uint64_t usage)
{
    m_usage = usage;
}

void account_t::set_fshare (double fshare)
{
    m_fshare = fshare;
}

const std::string &account_t::get_name () const
{
    return m_name;
}

bool account_t::is_user () const
{
    return m_is_user;
}

uint64_t account_t::get_shares () const
{
    return m_shares;
}

uint64_t account_t::get_usage () const
{
    return m_usage;
}

double account_t::get_fshare () const
{
    return m_fshare;
}

int account_t::dprint (std::ostringstream &out) const
{
    int rc = 0;
    try {
        out << "name: "     << m_name   << ", "
            << "shares: "   << m_shares << ", "
            << "usage: "    << m_usage  << ", "
            << "m_fshare: " << m_fshare << std::endl;
    } catch (std::bad_alloc &) {
        errno = ENOMEM;
        rc = -1;
    }
    return rc;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
