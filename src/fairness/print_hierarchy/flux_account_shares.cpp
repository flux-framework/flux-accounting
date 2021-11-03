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

#include "src/fairness/writer/data_writer_stdout.hpp"

using namespace Flux::accounting;
using namespace Flux::writer;

static void show_usage ()
{
    std::cout << "usage: flux shares [-P DELIMITER] [-p DB_PATH]\n"
              << "optional arguments:\n"
              << "\t-h,--help\t\t\tShow this help message\n"
              << "\t-P DELIMITER"
              << "\t\tPrint the database hierarchy in a parsable format\n"
              << "\t-p DB_PATH"
              << "\t\t\tSpecify location of the flux-accounting database"
              << std::endl;
}


int main (int argc, char** argv)
{
    std::string filepath = "";
    int rc = 0;
    std::shared_ptr<weighted_tree_node_t> root;
    std::string indent, delimiter = "";
    bool parsable = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-p") {
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

    data_writer_stdout_t data_writer (indent, parsable, delimiter);
    rc = data_writer.write_acct_info (filepath, root);

    return rc;
}
