/*
Copyright 2020 Lawrence Livermore National Security, LLC
(c.f. AUTHORS, NOTICE.LLNS, COPYING)

This file is part of the Flux resource manager framework.
For details, see https://github.com/flux-framework.

SPDX-License-Identifier: LGPL-3.0
*/

#ifndef WEIGHTED_TREE_HPP
#define WEIGHTED_TREE_HPP

#include <memory>
#include <vector>
#include "src/fairness/account/account.hpp"

namespace Flux {
namespace accounting {


/*! Weighted Tree Node Class:
 */
class weighted_tree_node_t : public account_t {
public:
    weighted_tree_node_t (std::shared_ptr<weighted_tree_node_t> parent,
                          const std::string &name, bool is_user,
                          uint64_t shares, uint64_t usage);

    uint64_t get_rank () const;
    uint64_t get_subtree_size () const;
    uint64_t get_subtree_leaf_size () const;
    double get_weight () const;
    std::shared_ptr<weighted_tree_node_t> get_child (size_t i) const;
    std::shared_ptr<weighted_tree_node_t> get_parent () const;

    bool is_tie_with_next () const;
    bool is_child_weight_equal_to_next (size_t i) const;
    bool is_leaf () const;

    void set_rank (uint64_t rank);
    void set_tie_with_next ();
    void unset_tie_with_next ();
    int add_child (std::shared_ptr<weighted_tree_node_t> child,
                   bool update_tree_metadata = true);
    int get_num_children () const;

    void sort_weighted_children ();
    void calc_and_sort_weighted_children ();

    int dprint_csv (std::ostringstream &out, int level, bool long_format) const;

private:
    friend class weighted_walk_t;

    bool is_equal (double a, double b) const;
    void calc_set_weight (uint64_t sibling_shares_sum,
                          uint64_t sibling_usage_sum);
    void calc_set_children_weight ();
    void propagate_subtree_size ();
    void propagate_subtree_leaf_size ();

    uint64_t m_rank = 0;
    uint64_t m_subtree_size = 1;
    uint64_t m_subtree_leaf_size = 0;
    double m_weight = 0.0f;
    bool m_tie_with_next = false;
    std::weak_ptr<weighted_tree_node_t> m_parent =
                                        std::weak_ptr<weighted_tree_node_t> ();
    std::vector<std::shared_ptr<weighted_tree_node_t>> m_children;
};


} // namespace accounting
} // namespace Flux

#endif // WEIGHTED_TREE_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
