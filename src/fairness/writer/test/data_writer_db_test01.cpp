/*****************************************************************************\
 *  Copyright (c) 2021 Lawrence Livermore National Security, LLC.  Produced at
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
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include <cmath>
#include <vector>
#include <tuple>

#include "src/fairness/reader/data_reader_db.hpp"
#include "src/fairness/writer/data_writer_db.hpp"
#include "src/common/libtap/tap.h"

using namespace Flux::accounting;
using namespace Flux::reader;
using namespace Flux::writer;

double fetch_fshare (sqlite3 *DB, const std::string &u, const std::string &b)
{
    std::string s;
    sqlite3_stmt *cs = nullptr;
    double fshare;

    s = "SELECT fairshare FROM association_table WHERE username=? AND bank=?";

    sqlite3_prepare_v2 (DB, s.c_str (), -1, &cs, 0);

    sqlite3_bind_text (cs, 1, u.c_str (), -1, NULL);
    sqlite3_bind_text (cs, 2, b.c_str (), -1, NULL);

    sqlite3_step (cs);

    fshare = sqlite3_column_double (cs, 0);

    sqlite3_finalize (cs);

    return fshare;
}

static void cmp_fshare_vals (const std::string &filename)
{
    bool bo = true;
    std::shared_ptr<weighted_tree_node_t> root;
    data_reader_db_t data_reader;
    data_writer_db_t data_writer;
    double epsilon = 0.000001f;
    sqlite3 *DB = nullptr;
    std::string username, bank;
    double fshare;

    sqlite3_open_v2 (filename.c_str (), &DB, SQLITE_OPEN_READWRITE, NULL);

    root = data_reader.load_accounting_db (filename);

    weighted_walk_t walker (root);
    walker.run ();

    data_writer.write_acct_info (filename, root);

    const auto &users = walker.get_users ();

    for (int i = 0; i < static_cast<int> (users.size ()); i++) {
        username = users[i]->get_name ();
        bank = users[i]->get_parent ()->get_name ();

        fshare = fetch_fshare (DB, username, bank);

        bo = bo && (fabs (users[i]->get_fshare () - fshare) < epsilon);
    }

    ok (bo, "%s: fairshare values are equal", filename.c_str ());

    sqlite3_close (DB);

    return;
}

static void test_small_no_tie (const std::string &acct_db_data_dir)
{
    cmp_fshare_vals (acct_db_data_dir + "/small_no_tie.db");
}

static void test_small_tie_zero_shares (const std::string &acct_db_data_dir)
{
    cmp_fshare_vals (acct_db_data_dir + "/small_tie_zero_shares.db");
}

static void test_small_tie (const std::string &acct_db_data_dir)
{
    cmp_fshare_vals (acct_db_data_dir + "/small_tie.db");
}

static void test_small_tie_all(const std::string &acct_db_data_dir)
{
    cmp_fshare_vals (acct_db_data_dir + "/small_tie_all.db");
}


int main(int argc, char *argv[])
{
    plan (4);

    std::string acct_db_data_dir = std::getenv("ACCOUNTING_TEST_DB_DIR");

    test_small_no_tie (acct_db_data_dir);

    test_small_tie_zero_shares (acct_db_data_dir);

    test_small_tie (acct_db_data_dir);

    test_small_tie_all (acct_db_data_dir);

    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
