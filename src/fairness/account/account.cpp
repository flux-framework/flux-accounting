/*****************************************************************************\
 *  Copyright (c) 2020 Lawrence Livermore National Security, LLC.  Produced at
 *  the Lawrence Livermore National Laboratory (cf, AUTHORS, DISCLAIMER.LLNS).
 *  LLNL-CODE-658032 All rights reserved.
 *
 *  This file is part of the Flux resource manager framework.
 *  For details, see https://github.com/flux-framework.
 *
 *  This program is free software; you can redistribute it and/or modify it
 *  under the terms of the GNU General Public License as published by the Free
 *  Software Foundation; either version 2 of the license, or (at your option)
 *  any later version.
 *
 *  Flux is distributed in the hope that it will be useful, but WITHOUT
 *  ANY WARRANTY; without even the IMPLIED WARRANTY OF MERCHANTABILITY or
 *  FITNESS FOR A PARTICULAR PURPOSE.  See the terms and conditions of the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License along
 *  with this program; if not, write to the Free Software Foundation, Inc.,
 *  59 Temple Place, Suite 330, Boston, MA 02111-1307 USA.
 *  See also:  http://www.gnu.org/licenses/
\*****************************************************************************/

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
