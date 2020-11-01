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

#ifndef WEIGHTED_WALK_HPP
#define WEIGHTED_WALK_HPP

#include "src/fairness/weighted_tree/weighted_tree.hpp"

namespace Flux {
namespace accounting {


/*! Account Tree Walker Class:
 */
class weighted_walk_t {
public:

    weighted_walk_t (std::shared_ptr<weighted_tree_node_t> root);

    uint64_t get_tree_size () const;
    uint64_t get_tree_leaf_size () const;
    const std::vector<
              std::shared_ptr<weighted_tree_node_t>> & get_users () const;

    int run ();
    int dprint_csv (std::ostream &os, bool long_format = false);

private:
    int dprint_csv (std::ostream &os,
                    std::shared_ptr<weighted_tree_node_t> &n, bool long_format);
    int handle_leaf (std::shared_ptr<weighted_tree_node_t> &n);
    int dprint_leaf (std::ostream &os,
                     std::shared_ptr<weighted_tree_node_t> &n,
                     bool long_format);

    int merge_grand_children (std::shared_ptr<weighted_tree_node_t> &vc,
                              std::shared_ptr<weighted_tree_node_t> &c);
    int build_tie_aware_children (std::shared_ptr<weighted_tree_node_t> &n,
                                  std::vector<
                                      std::shared_ptr<
                                          weighted_tree_node_t>> &
                                              tie_aware_children);
    int handle_internal (std::shared_ptr<weighted_tree_node_t> &n);
    int dprint_internal (std::ostream &os,
                         std::shared_ptr<weighted_tree_node_t> &n,
                         bool long_format);

    int weighted_depth_first_visit (std::shared_ptr<weighted_tree_node_t> &n);
    int dprint_depth_first_visit (std::ostream &os,
                                  std::shared_ptr<weighted_tree_node_t> &n,
                                  bool long_format);

    int m_level = 0;
    uint64_t m_current_rank = 0;
    uint64_t m_stride_size = 0;
    std::shared_ptr<weighted_tree_node_t> m_root;
    std::vector<std::shared_ptr<weighted_tree_node_t>> m_users;
};


} // namespace accounting
} // namespace Flux

#endif // WEIGHTED_WALK_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
