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
#include "src/fairness/writer/data_writer_db.hpp"

using namespace Flux::accounting;
using namespace Flux::reader;
using namespace Flux::writer;

const std::string DBPATH = std::string (X_LOCALSTATEDIR) + "/FluxAccounting.db";

static void show_usage ()
{
    std::cout << "usage: flux update-fshare [-p DB_PATH]\n"
              << "optional arguments:\n"
              << "\t-h,--help\t\t\tShow this help message\n"
              << "\t-p DB_PATH"
              << "\t\t\tSpecify location of the flux-accounting database"
              << std::endl;
}


int main (int argc, char** argv)
{
    std::shared_ptr<weighted_tree_node_t> root;
    data_reader_db_t data_reader;
    data_writer_db_t data_writer;
    std::string filepath;
    int rc;

    // const std::string *err_msg;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-p") {
            filepath = argv[i + 1];
            i++;
        } else {
            show_usage ();
            rc = -1;
            return rc;
        }
    }

    if (filepath == "")
        filepath = DBPATH;

    root = data_reader.load_accounting_db (filepath);

    if (root == nullptr) {
        std::string e_msg = data_reader.err_message ();
        std::cout << e_msg << std::endl;
        return -1;
    }

    weighted_walk_t walker (root);

    if (walker.run () < 0) {
        std::cout << "Unable to calculate fairshare values" << std::endl;
        return -1;
    }

    if (data_writer.write_acct_info (filepath, root) < 0) {
        std::string e_msg = data_writer.err_message ();
        std::cout << e_msg << std::endl;
        return -1;
    }

    return 0;
}
