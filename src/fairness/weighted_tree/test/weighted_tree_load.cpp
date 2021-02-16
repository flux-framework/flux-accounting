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

#if HAVE_CONFIG_H
# include <config.h>
#endif

#include <cerrno>
#include <deque>
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include "src/fairness/weighted_tree/test/weighted_tree_load.hpp"

using namespace Flux::accounting;

int load_weighted_tree (const std::string &path,
                        std::shared_ptr<weighted_tree_node_t> &root_out)
{
    int rc = 0;
    int64_t level = -1;
    std::string line;
    std::ifstream in_file (path);
    std::shared_ptr<weighted_tree_node_t> node = nullptr;
    std::deque<std::shared_ptr<weighted_tree_node_t>> ancestors;

    if (!in_file) {
        errno = EINVAL;
        return -1;
    }

    while (std::getline (in_file, line)) {
        bool is_user = true;
        std::string token;
        std::stringstream ss (line);
        std::vector<std::string> result;
        int64_t clevel = 0, offset = 0;

        while (std::getline (ss, token, ','))
            result.push_back (token);

        if (result.size () != 5) {
            errno = EINVAL;
            rc = -1;
            goto done;
        }
        if (result[2] == "%^+_nouser")
            is_user = false;

        clevel = static_cast<int64_t> (std::stoll (result[0]));
        if ( (offset = (clevel - level)) > 1) {
            errno = EINVAL;
            rc = -1;
            goto done;
        }

        node = std::make_shared<weighted_tree_node_t> (
                        ancestors.empty ()? nullptr : ancestors.back (),
                        is_user? result[2] : result[1],
                        is_user,
                        std::stoll (result[3]), std::stoll (result[4]));
        if (ancestors.empty ()) {
            if (is_user) {
                errno = EINVAL;
                rc = -1;
                goto done;
            }
            ancestors.push_back (node);
            level = clevel;
            continue;
        }
        for (int i = 0; i < (-offset + 1); ++i)
            ancestors.pop_back ();
        if ( (rc = ancestors.back ()->add_child (node)) < 0)
            goto done;
        if (!is_user) {
            ancestors.push_back (node);
            level = clevel;
        }
    }

    if (!ancestors.empty ()) {
        root_out = ancestors.front ();
    }

done:
    in_file.close ();
    return rc;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
