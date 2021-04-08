/************************************************************\
 * Copyright 2020 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include <algorithm>
#include "src/fairness/weighted_tree/weighted_walk.hpp"

using namespace Flux::accounting;


/******************************************************************************
 *                                                                            *
 *                  Private Methods of Weighted Walk Class                    *
 *                                                                            *
 ******************************************************************************/

int weighted_walk_t::dprint_csv (std::ostream &os,
                                 std::shared_ptr<weighted_tree_node_t> &n,
                                 bool long_format)
{
    int rc = 0;
    std::ostringstream out;
    if ( (rc = n->dprint_csv (out, m_level - 1, long_format)) < 0)
        return rc;
    if (long_format)
        out << "," << n->get_weight ();
    os << out.str () << std::endl;
    return rc;
}

int weighted_walk_t::handle_leaf (std::shared_ptr<weighted_tree_node_t> &n)
{
    if (n->is_user ()) {
        double fshare = static_cast<double> (m_current_rank)
                        / static_cast<double> (get_tree_leaf_size ());
        n->set_fshare (fshare);
        if (m_current_rank == 0) {
            errno = ERANGE;
            return -1;
        }
        if (n->is_tie_with_next ()) {
            m_stride_size++;
            n->unset_tie_with_next ();
        } else {
            m_current_rank = m_current_rank - 1 - m_stride_size;
            m_stride_size = 0;
        }
        m_users.push_back (n);
    }
    return 0;
}

int weighted_walk_t::dprint_leaf (std::ostream &os,
                                  std::shared_ptr<weighted_tree_node_t> &n,
                                  bool long_format)
{
    int rc = 0;
    if ( (rc = dprint_csv (os, n, long_format)) < 0)
        return rc;
    return rc;
}

int weighted_walk_t::merge_grand_children (
                         std::shared_ptr<weighted_tree_node_t> &vc,
                         std::shared_ptr<weighted_tree_node_t> &child)
{
    int i = 0;
    int rc = 0;
    if (vc == nullptr || child == nullptr) {
        errno = EINVAL;
        return -1;
    }
    for (i = 0; i < child->get_num_children (); i++) {
        if ( (rc = vc->add_child (child->get_child (i), false)) < 0)
            return rc;
    }
    return rc;
}

int weighted_walk_t::build_tie_aware_children (
        std::shared_ptr<weighted_tree_node_t> &n,
        std::vector<std::shared_ptr<weighted_tree_node_t>> &tie_aware_children)
{
    int i = 0;
    int rc = 0;
    bool stride = false;
    std::shared_ptr<weighted_tree_node_t> vc = nullptr;

    for (i = 0; i < n->get_num_children (); i++) {
        std::shared_ptr<weighted_tree_node_t> &child = n->m_children[i];
        if (child->is_user ()) {
            if (n->is_child_weight_equal_to_next (i))
                child->set_tie_with_next ();
            tie_aware_children.push_back (child);
            continue;
        }

        if (n->is_child_weight_equal_to_next (i)) {
            if (!stride) { // a new stride detected
                stride = true;
                vc = std::make_shared<weighted_tree_node_t> (nullptr,
                                                             "v", false, 0, 0);
            }
            // in the middle of striding
            if ( (rc = merge_grand_children (vc, child)) < 0)
                return rc;
        } else {
            if (stride) { // the end of a stride detected
                if ( (rc = merge_grand_children (vc, child)) < 0)
                    return rc;
                vc->sort_weighted_children ();
                tie_aware_children.push_back (vc);
                stride = false;
                vc = nullptr;
             } else { // if no stride add the child as is
                 tie_aware_children.push_back (child);
             }
        }
    }
    return rc;
}

int weighted_walk_t::handle_internal (std::shared_ptr<weighted_tree_node_t> &n)
{
    int i = 0;
    int rc = 0;
    std::vector<std::shared_ptr<weighted_tree_node_t>> tie_aware_children;

    // Sort all of the grand children (with respect to their original parent)
    for (i = 0; i < n->get_num_children (); i++)
        n->get_child (i)->calc_and_sort_weighted_children ();

    // build tie-aware children vector
    // Carefully handle ties by creating a new "virtual" child node and merge
    // the children of the tied children into that new child node object.
    // This enables us to visit the grand children of those tied children fairly.
    if ( (rc = build_tie_aware_children (n, tie_aware_children)) < 0)
        return 0;

    // descent into children
    for (auto &child : tie_aware_children) {
        if ( (rc = weighted_depth_first_visit (child)) < 0)
            return rc;
    }
    return rc;
}

int weighted_walk_t::dprint_internal (std::ostream &os,
                                      std::shared_ptr<weighted_tree_node_t> &n,
                                      bool long_format)
{
    int rc = 0;
    if ( (rc = dprint_csv (os, n, long_format)) < 0)
        return rc;
    for (auto &child : n->m_children) {
        if ( (rc = dprint_depth_first_visit (os, child, long_format)) < 0) {
            return rc;
        }
    }
    return rc;
}

int weighted_walk_t::weighted_depth_first_visit (std::shared_ptr<
                                                     weighted_tree_node_t> &n)
{
    int rc = 0;
    m_level++;
    rc = (n->is_leaf ())? handle_leaf (n)
                        : handle_internal (n);
    m_level--;
    return rc;
}

int weighted_walk_t::dprint_depth_first_visit (std::ostream &os,
                                               std::shared_ptr<
                                                   weighted_tree_node_t> &n,
                                               bool long_format)
{
    int rc = 0;
    m_level++;
    rc = (n->is_leaf ())? dprint_leaf (os, n, long_format)
                        : dprint_internal (os, n, long_format);
    m_level--;
    return rc;
}


/******************************************************************************
 *                                                                            *
 *                  Public Methods of Weighted Walk Class                     *
 *                                                                            *
 ******************************************************************************/

weighted_walk_t::weighted_walk_t (std::shared_ptr<weighted_tree_node_t> root)
{
    m_root = root;
}

uint64_t weighted_walk_t::get_tree_size () const
{
    if (!m_root)
        return -1;
    return m_root->get_subtree_size ();
}

uint64_t weighted_walk_t::get_tree_leaf_size () const
{
    if (!m_root)
        return -1;
    return m_root->get_subtree_leaf_size ();
}

int weighted_walk_t::run ()
{
    int rc = 0;

    if (!m_root)
        return -1;

    m_level = 0;
    m_current_rank = get_tree_leaf_size ();
    m_users.clear ();

    // Sort m_root's children (so grand children at this function).
    // weighted_depth_first_visit assumes that the children
    // of the passed node already have their weight calculated
    // and sorted by the previous recursive call.
    // It is important to handle ties carefully. Please see
    // further comments in weighted_depth_first_visit regarding
    // tie handling.
    m_root->calc_and_sort_weighted_children ();
    if ( (rc = weighted_depth_first_visit (m_root)) < 0)
        return rc;
    std::sort (m_users.begin (), m_users.end (),
               [] (std::shared_ptr<weighted_tree_node_t> &a,
                   std::shared_ptr<weighted_tree_node_t> &b) {
                   return a->get_fshare () > b->get_fshare ();
               });
    return rc;
}

const std::vector<std::shared_ptr<weighted_tree_node_t>> &
    weighted_walk_t::get_users () const
{
    return m_users;
}

int weighted_walk_t::dprint_csv (std::ostream &os, bool long_format)
{
    m_level = 0;
    if (!m_root)
        return -1;
    return dprint_depth_first_visit (os, m_root, long_format);
}


/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
