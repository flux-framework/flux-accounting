/*
Copyright 2020 Lawrence Livermore National Security, LLC
(c.f. AUTHORS, NOTICE.LLNS, COPYING)

This file is part of the Flux resource manager framework.
For details, see https://github.com/flux-framework.

SPDX-License-Identifier: LGPL-3.0
*/

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
