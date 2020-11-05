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

#ifndef ACCOUNT_HPP
#define ACCOUNT_HPP

#include <string>
#include <sstream>
#include <cstdint>
#include <limits>

namespace Flux {
namespace accounting {

/*! Account Class:
 */
class account_t {
public:
    account_t (const std::string &name,
               bool is_user, uint64_t shares, uint64_t usage);

    void set_name (const std::string &name);
    void set_shares (uint64_t shares);
    void set_usage (uint64_t usage);
    void set_fshare (double fshare);

    const std::string &get_name () const;
    bool is_user () const;
    uint64_t get_shares () const;
    uint64_t get_usage () const;
    double get_fshare () const;

    int dprint (std::ostringstream &out) const;

private:
    std::string m_name = "";
    bool m_is_user = false;
    uint64_t m_shares = 0;
    uint64_t m_usage = std::numeric_limits<uint64_t>::max ();
    double m_fshare = 0.0f;
};

} // namespace accounting
} // namespace Flux

#endif // ACCOUNT_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
