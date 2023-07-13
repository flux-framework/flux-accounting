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

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <string>

#include "src/fairness/reader/data_reader_db.hpp"
#include "src/common/libtap/tap.h"

using namespace Flux::accounting;
using namespace Flux::reader;

static void test_fairshare_order (const std::string &filename,
                                  const std::vector<std::string> &expected)
{
    bool bo = true;
    std::shared_ptr<weighted_tree_node_t> root;
    data_reader_db_t data_reader;

    root = data_reader.load_accounting_db (filename);

    weighted_walk_t walker (root);
    walker.run ();

    const auto &users = walker.get_users ();

    for (int i = 0; i < static_cast<int> (users.size ()); i++) {
        bo = bo && (users[i]->get_name () == expected[i]);
    }

    ok (bo, "%s: fairshare order is correct", filename.c_str ());

    return;
}

static void test_small_no_tie (const std::string &accounting_db_data_dir)
{
    std::string filename = accounting_db_data_dir + "/small_no_tie.db";

    std::vector<std::string> expected;
    expected.push_back ("leaf.3.1");
    expected.push_back ("leaf.3.2");
    expected.push_back ("leaf.2.1");
    expected.push_back ("leaf.2.2");
    expected.push_back ("leaf.1.3");
    expected.push_back ("leaf.1.1");
    expected.push_back ("leaf.1.2");

    test_fairshare_order (filename, expected);
}

static void test_small_tie_zero_shares (
                                const std::string &accounting_db_data_dir)
{
    std::string filename = accounting_db_data_dir + "/small_tie_zero_shares.db";

    std::vector<std::string> expected;
    expected.push_back ("leaf.3.1");
    expected.push_back ("leaf.3.2");
    expected.push_back ("leaf.2.3");
    expected.push_back ("leaf.1.3");
    expected.push_back ("leaf.1.2");
    expected.push_back ("leaf.1.1");
    expected.push_back ("leaf.2.1");
    expected.push_back ("leaf.2.2");

    test_fairshare_order (filename, expected);
}

static void test_small_tie (const std::string &accounting_db_data_dir)
{
    std::string filename = accounting_db_data_dir + "/small_tie.db";

    std::vector<std::string> expected;
    expected.push_back ("leaf.3.1");
    expected.push_back ("leaf.3.2");
    expected.push_back ("leaf.1.3");
    expected.push_back ("leaf.2.3");
    expected.push_back ("leaf.1.2");
    expected.push_back ("leaf.2.2");
    expected.push_back ("leaf.1.1");
    expected.push_back ("leaf.2.1");

    test_fairshare_order (filename, expected);
}

static void test_small_tie_all(const std::string &accounting_db_data_dir)
{
    std::string filename = accounting_db_data_dir + "/small_tie_all.db";

    std::vector<std::string> expected;
    expected.push_back ("leaf.1.3");
    expected.push_back ("leaf.2.3");
    expected.push_back ("leaf.3.3");
    expected.push_back ("leaf.1.2");
    expected.push_back ("leaf.2.2");
    expected.push_back ("leaf.3.2");
    expected.push_back ("leaf.1.1");
    expected.push_back ("leaf.2.1");
    expected.push_back ("leaf.3.1");

    test_fairshare_order (filename, expected);
}

int main(int argc, char *argv[])
{
    plan (4);

    std::string accounting_db_data_dir = std::getenv("ACCOUNTING_DB_DATA_DIR");

    test_small_no_tie (accounting_db_data_dir);

    test_small_tie_zero_shares (accounting_db_data_dir);

    test_small_tie (accounting_db_data_dir);

    test_small_tie_all(accounting_db_data_dir);

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
