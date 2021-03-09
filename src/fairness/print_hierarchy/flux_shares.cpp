/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/
#include <iostream>
#include <iomanip>

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include "src/fairness/reader/data_reader_db.hpp"

using namespace Flux::accounting;
using namespace Flux::reader;

const std::string DBPATH = std::string (X_LOCALSTATEDIR) + "/FluxAccounting.db";

static void show_usage ()
{
    std::cout << "usage: flux shares [-P DELIMITER] [-f DB_PATH]\n"
              << "optional arguments:\n"
              << "\t-h,--help\t\t\tShow this help message\n"
              << "\t-P DELIMITER"
              << "\t\tPrint the database hierarchy in a parsable format\n"
              << "\t-f DB_PATH"
              << "\t\t\tSpecify location of the flux-accounting database"
              << std::endl;
}

void print_csv_header (const std::string& delimiter="|")
{
    std::cout << "Account" << delimiter
              << "Username" << delimiter
              << "RawShares" << delimiter
              << "RawUsage"
              << std::endl;
}

void print_csv (std::shared_ptr<weighted_tree_node_t> node,
                const std::string& indent,
                const std::string& delimiter="|")
{

    if (node == nullptr)
        return;

    // print node data
    if (node->is_user ()) {
        std::cout << indent << node->get_parent ()-> get_name () << delimiter
                  << node->get_name () << delimiter
                  << node->get_shares () << delimiter
                  << node->get_usage ()
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

void pretty_print_header ()
{
    std::cout << std::setw(20) << std::left << "Account"
              << std::setw(20) << std::right << "Username"
              << std::setw(20) << std::right << "RawShares"
              << std::setw(20) << std::right << "RawUsage"
              << std::endl;
}

void pretty_print (std::shared_ptr<weighted_tree_node_t> node,
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

std::shared_ptr<weighted_tree_node_t> read_from_db (const std::string &filename)
{
    data_reader_db_t data_reader;
    std::shared_ptr<weighted_tree_node_t> root;

    root = data_reader.load_accounting_db (filename);
    if (root == nullptr)
        return nullptr;

    return root;
}


int main (int argc, char** argv)
{
    bool parsable = false;
    std::string filepath, delimiter, indent = "";
    int rc = 0;
    std::shared_ptr<weighted_tree_node_t> root;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-f") {
            filepath = argv[i + 1];
            i++;
        } else if (arg == "-P") {
            parsable = true;
            if (std::string (argv[i + 1]).length () > 1) {
                rc = -1;
                return rc;
            }
            delimiter = std::string (argv[i + 1]);
            i++;
        } else if (arg == "-h" || arg == "--help") {
            show_usage ();
            return rc;
        } else {
            show_usage ();
            rc = -1;
            return rc;
        }
    }

    if (filepath == "")
        filepath = DBPATH;

    root = read_from_db (filepath);
    if (root == nullptr) {
        rc = -1;
        return rc;
    }

    if (parsable) {
        print_csv_header (delimiter);
        print_csv(root, indent, delimiter);
    } else {
        pretty_print_header ();
        pretty_print (root, indent);
    }

    return rc;
}
