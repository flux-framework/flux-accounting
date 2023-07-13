/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/
#if HAVE_CONFIG_H
#include "config.h"
#endif

#include <iostream>
#include <iomanip>

#include "src/fairness/writer/data_writer_stdout.hpp"

using namespace Flux::accounting;
using namespace Flux::writer;
using namespace Flux::reader;

/******************************************************************************
 *                                                                            *
 *                          Private DB Writer API                             *
 *                                                                            *
 *****************************************************************************/

std::shared_ptr<weighted_tree_node_t> read_from_db (const std::string &filename)
{
    std::string DBPATH = std::string (X_LOCALSTATEDIR) + "/FluxAccounting.db";

    data_reader_db_t data_reader;
    std::shared_ptr<weighted_tree_node_t> root;

    root = (filename == "") ? data_reader.load_accounting_db (DBPATH) :
        data_reader.load_accounting_db (filename);

    if (root == nullptr)
        return nullptr;

    return root;
}


void data_writer_stdout_t::print_csv_header (const std::string& delimiter)
{
    std::cout << "Account" << delimiter
              << "Username" << delimiter
              << "RawShares" << delimiter
              << "RawUsage" << delimiter
              << "Fairshare"
              << std::endl;
}


void data_writer_stdout_t::print_csv (
                                    std::shared_ptr<weighted_tree_node_t> node,
                                    const std::string& indent,
                                    const std::string& delimiter)
{

    if (node == nullptr)
        return;

    // print node data
    if (node->is_user ()) {
        std::cout << indent << node->get_parent ()-> get_name () << delimiter
                  << node->get_name () << delimiter
                  << node->get_shares () << delimiter
                  << node->get_usage () << delimiter
                  << node->get_fshare ()
                  << std::endl;
    } else {
        std::cout << indent << node->get_name () << delimiter << delimiter
                  << node->get_shares () << delimiter
                  << node->get_usage ()
                  << std::endl;
    }

    // recur on subtree
    for (int i = 0; i < node->get_num_children(); i++) {
        print_csv(node->get_child (i), indent + " ", delimiter);
    }
}


void data_writer_stdout_t::pretty_print_header ()
{
    std::cout << std::setw(20) << std::left << "Account"
              << std::setw(20) << std::right << "Username"
              << std::setw(20) << std::right << "RawShares"
              << std::setw(20) << std::right << "RawUsage"
              << std::setw(20) << std::right << "Fairshare"
              << std::endl;
}


void data_writer_stdout_t::pretty_print (
                                    std::shared_ptr<weighted_tree_node_t> node,
                                    const std::string& indent)
{
    std::string name;

    if (node == nullptr)
        return;

    // print node data
    if (node->is_user ()) {
        name = indent + node->get_parent ()->get_name ();
        std::cout << std::setw(20) << std::left << name
                  << std::setw(20) << std::right << node->get_name ()
                  << std::setw(20) << std::right << node->get_shares ()
                  << std::setw(20) << std::right << node->get_usage ()
                  << std::setw(20) << std::right << node->get_fshare ()
                  << std::endl;
    } else {
        name = indent + node->get_name ();
        std::cout << std::setw(20) << std::left << name
                  << std::setw(20) << std::right << ""
                  << std::setw(20) << std::right << node->get_shares ()
                  << std::setw(20) << std::right << node->get_usage ()
                  << std::endl;
    }

    // recur on subtree
    for (int i = 0; i < node->get_num_children(); i++) {
        pretty_print(node->get_child (i), indent + " ");
    }
}


/******************************************************************************
 *                                                                            *
 *                         Public DB Writer API                               *
 *                                                                            *
 *****************************************************************************/

int data_writer_stdout_t::write_acct_info (
                                    const std::string &path,
                                    std::shared_ptr<weighted_tree_node_t> node)
{

    std::shared_ptr<weighted_tree_node_t> root;
    int rc = 0;

    root = read_from_db (path);
    if (root == nullptr) {
        rc = -1;
        return rc;
    }

    if (this->m_parsable) {
        print_csv_header (this->m_delimiter);
        print_csv (root, this->m_indent, this->m_delimiter);
    } else {
        pretty_print_header ();
        pretty_print (root, this->m_indent);
    }

    return 0;
}
