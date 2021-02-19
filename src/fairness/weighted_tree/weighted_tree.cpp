/*
Copyright 2020 Lawrence Livermore National Security, LLC
(c.f. AUTHORS, NOTICE.LLNS, COPYING)

This file is part of the Flux resource manager framework.
For details, see https://github.com/flux-framework.

SPDX-License-Identifier: LGPL-3.0
*/

#include <cmath>
#include <cerrno>
#include <limits>
#include <numeric>
#include <algorithm>
#include "src/fairness/weighted_tree/weighted_tree.hpp"

using namespace Flux::accounting;


/******************************************************************************
 *                                                                            *
 *               Private Methods of Weighted Tree Node Class                  *
 *                                                                            *
 ******************************************************************************/

bool weighted_tree_node_t::is_equal (double a, double b) const
{
    // The following is one of the most reliable and simple
    // ways to check the floating-point equality.
    // The absolute tolerance test fails when a and b are large,
    // and the relative tolerance test fails when they are small.
    // The following combines these two tests together.
    // Please refer to page 443 of the collision detection book:
    //     http://realtimecollisiondetection.net/books/rtcd/
    double threshold = std::numeric_limits<double>::epsilon ()
                          * std::max (fabs (a), std::max (fabs (b), 1.0));
    return fabs (a - b) < threshold;
}

void weighted_tree_node_t::calc_set_weight (uint64_t sibling_shares_sum,
                                            uint64_t sibling_usage_sum)
{
    double s_weight, u_weight;

    if (get_shares () == 0) {
        // if shares are not non-zero, sibling_shares_sum is guaranteed
        // to be non-zero
        m_weight = 0.0f;
    } else if (get_usage () == 0) {
        // if usage is zero, we must give the highest weight
        // one higher than 1.0/(1.0/MAX_UINT64)
        m_weight = static_cast<double> (std::numeric_limits<uint64_t>::max ());
        m_weight += 1.0f;
    } else {
        s_weight = static_cast<double> (get_shares ())
                       / static_cast<double> (sibling_shares_sum);
        u_weight = static_cast<double> (get_usage ())
                       / static_cast<double> (sibling_usage_sum);

        // The higher the given shares relative to the shares
        // of its siblings and
        // the lower the usage is relative to the usage
        // of its siblings, m_weight gets larger.
        m_weight = s_weight / u_weight;
    }
}

void weighted_tree_node_t::calc_set_children_weight ()
{
    // Calculate the total shares and usage across sibling accounts
    auto total = std::accumulate (
                     m_children.begin (),
                     m_children.end (),
                     std::pair<uint64_t, uint64_t> (0, 0),
                     [] (const std::pair<uint64_t, uint64_t> &a,
                         const std::shared_ptr<weighted_tree_node_t> &b) {
                         uint64_t s_sum = a.first + b->get_shares ();
                         uint64_t u_sum = a.second + b->get_usage ();
                         return std::make_pair (s_sum, u_sum);
                     });
    // total.first: sibling_shares_sum
    // total.second: sibling_usage_sum
    for (auto &child : m_children)
        child->calc_set_weight (total.first, total.second);
}

void weighted_tree_node_t::propagate_subtree_size ()
{
    if (m_parent.expired ())
        return;
    m_parent.lock ()->m_subtree_size++;
    m_parent.lock ()->propagate_subtree_size ();
}

void weighted_tree_node_t::propagate_subtree_leaf_size ()
{
    if (m_parent.expired ())
        return;
    m_parent.lock ()->m_subtree_leaf_size++;
    m_parent.lock ()->propagate_subtree_leaf_size ();
}


/******************************************************************************
 *                                                                            *
 *               Public Methods of Weighted Tree Node Class                   *
 *                                                                            *
 ******************************************************************************/

weighted_tree_node_t::weighted_tree_node_t (
    std::shared_ptr<weighted_tree_node_t> parent, const std::string &name,
    bool is_user, uint64_t shares, uint64_t usage)
    : account_t (name, is_user, shares, usage)
{
    m_parent = parent;
    m_subtree_size = 1;
    if (is_user)
        m_subtree_leaf_size = 1;
}

uint64_t weighted_tree_node_t::get_rank () const
{
    return m_rank;
}

uint64_t weighted_tree_node_t::get_subtree_size () const
{
    return m_subtree_size;
}

uint64_t weighted_tree_node_t::get_subtree_leaf_size () const
{
    return m_subtree_leaf_size;
}

double weighted_tree_node_t::get_weight () const
{
    return m_weight;
}

std::shared_ptr<weighted_tree_node_t> weighted_tree_node_t
                                          ::get_child (size_t i) const
{
    if (i >= m_children.size ())
        return nullptr;
    return m_children[i];
}

std::shared_ptr<weighted_tree_node_t> weighted_tree_node_t
                                          ::get_parent () const
{
    return m_parent.lock ();
}

bool weighted_tree_node_t::is_tie_with_next () const
{
    return m_tie_with_next;
}

bool weighted_tree_node_t::is_leaf () const
{
    return m_children.empty ();
}

void weighted_tree_node_t::set_rank (uint64_t rank)
{
    m_rank = rank;
}

void weighted_tree_node_t::set_tie_with_next ()
{
    m_tie_with_next = true;
}

void weighted_tree_node_t::unset_tie_with_next ()
{
    m_tie_with_next = false;
}

int weighted_tree_node_t::add_child (std::shared_ptr<weighted_tree_node_t> c,
                                     bool update_metadata)
{
    int rc = 0;
    try {
        m_children.push_back (c);
        if (update_metadata) {
            m_subtree_size++;
            propagate_subtree_size ();
            if (c->is_user ()) {
                m_subtree_leaf_size++;
                propagate_subtree_leaf_size ();
            }
        }
    } catch (std::bad_alloc &) {
        errno = ENOMEM;
        rc = -1;
    }
    return rc;
}

bool weighted_tree_node_t::is_child_weight_equal_to_next (size_t i) const
{
    if (m_children.empty () || i >= (m_children.size () - 1))
        return false;
    if (m_children[i]->is_user () != m_children[i+1]->is_user ())
        return false;
    return is_equal (m_children[i]->get_weight (),
                     m_children[i+1]->get_weight ());
}

int weighted_tree_node_t::get_num_children () const
{
    return static_cast<int> (m_children.size ());
}

void weighted_tree_node_t::sort_weighted_children ()
{
    std::sort (m_children.begin (), m_children.end (),
               [this] (std::shared_ptr<weighted_tree_node_t> &a,
                   std::shared_ptr<weighted_tree_node_t> &b) {
                   if (is_equal (a->get_weight (), b->get_weight ()) ) {
                       if (a->is_user () && !b->is_user ())
                           return true;
                       else if (!a->is_user () && b->is_user ())
                           return false;
                   }
                   return a->get_weight () > b->get_weight ();
               });
}

void weighted_tree_node_t::calc_and_sort_weighted_children ()
{
    calc_set_children_weight ();
    sort_weighted_children ();
}

int weighted_tree_node_t::dprint_csv (std::ostringstream &out,
                                      int level, bool long_format) const
{
    int rc = 0;
    try {
        if (is_user ()) {
            if (m_parent.expired ()) {
                errno = EINVAL;
                return -1;
            }
            out << level << "," << m_parent.lock ()->get_name () << ","
                << get_name () << "," << get_shares () << "," << get_usage ();
            if (long_format)
                out << "," << get_fshare();
        } else {
            out << level << "," << get_name () << ","
                << "%^+_nouser" << "," << get_shares () << "," << get_usage ();
            if (long_format)
                out << "," << get_fshare();
        }
    } catch (std::bad_alloc &) {
        errno = ENOMEM;
        rc = -1;
    }
    return rc;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
