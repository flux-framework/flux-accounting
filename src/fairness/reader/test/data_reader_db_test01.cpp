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

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <string>

#include "src/fairness/reader/data_reader_db.hpp"
#include "src/common/libtap/tap.h"

using namespace Flux::accounting;

static void test_fairshare_order (const std::string &filename,
                                  const std::vector<std::string> &expected)
{
    bool bo = true;
    std::shared_ptr<weighted_tree_node_t> root;

    root = load_accounting_db (filename);

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
