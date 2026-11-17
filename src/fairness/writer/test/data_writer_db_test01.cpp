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
#include <cerrno>
#include <cstdlib>
#include <vector>
#include <tuple>
#include <unistd.h>

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

static bool check_fshare (sqlite3 *DB, const std::string &username,
                         double expected)
{
    sqlite3_stmt *stmt = nullptr;
    const char *sql = "SELECT fairshare FROM association_table "
                      "WHERE username=? AND bank='root'";
    bool matches = false;
    int rc;

    rc = sqlite3_prepare_v2 (DB, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK)
        goto done;
    rc = sqlite3_bind_text (stmt, 1, username.c_str (), -1, SQLITE_TRANSIENT);
    if (rc != SQLITE_OK)
        goto done;
    rc = sqlite3_step (stmt);
    if (rc != SQLITE_ROW)
        goto done;

    matches = sqlite3_column_type (stmt, 0) == SQLITE_FLOAT
              && sqlite3_column_double (stmt, 0) == expected;
    rc = sqlite3_step (stmt);
    if (rc != SQLITE_DONE)
        matches = false;
done:
    if (rc != SQLITE_DONE)
        diag ("fairshare query failed: %s", sqlite3_errmsg (DB));
    if (sqlite3_finalize (stmt) != SQLITE_OK)
        matches = false;
    return matches;
}

static void test_double_binding ()
{
    const char *tmpdir = std::getenv ("TMPDIR");
    std::string path = std::string (tmpdir && *tmpdir ? tmpdir : "/tmp")
                       + "/flux-accounting-fshare-XXXXXX";
    sqlite3 *DB = nullptr;
    data_writer_db_t writer;
    auto root = std::make_shared<weighted_tree_node_t> (
                                            nullptr, "root", false, 1, 0.0);
    std::vector<std::shared_ptr<weighted_tree_node_t>> users;
    const double values[][4] = {
        {0.0, 1.0, 1.0 / 3.0, 0.000000123456789},
        {1.0 / 7.0, 0.0, 1.0, 0.123456789}
    };
    // values are rounded to six decimal places when written
    const double expected[][4] = {
        {0.0, 1.0, 0.333333, 0.0},
        {0.142857, 0.0, 1.0, 0.123457}
    };
    const char *sql = "CREATE TABLE association_table ("
                      "username TEXT NOT NULL, bank TEXT NOT NULL, "
                      "fairshare REAL NOT NULL DEFAULT 0.5, "
                      "PRIMARY KEY (username, bank)); "
                      "INSERT INTO association_table (username, bank) VALUES "
                      "('user0', 'root'), ('user1', 'root'), "
                      "('user2', 'root'), ('user3', 'root');";
    bool cleaned = true;
    int fd = mkstemp (&path[0]);
    int rc;

    if (fd < 0) {
        ok (false, "create temporary fairshare database");
        return;
    }
    if (close (fd) < 0) {
        ok (false, "close temporary fairshare database file");
        goto done;
    }
    rc = sqlite3_open_v2 (path.c_str (), &DB, SQLITE_OPEN_READWRITE, nullptr);
    if (rc == SQLITE_OK)
        rc = sqlite3_exec (DB, sql, nullptr, nullptr, nullptr);
    if (rc != SQLITE_OK) {
        diag ("fairshare database setup failed: %s", sqlite3_errmsg (DB));
        ok (false, "set up temporary fairshare database");
        goto done;
    }
    for (int i = 0; i < 4; i++) {
        auto user = std::make_shared<weighted_tree_node_t> (
                             root, "user" + std::to_string (i), true, 1, 0.0);
        if (root->add_child (user) < 0) {
            ok (false, "set up fairshare tree");
            goto done;
        }
        users.push_back (user);
    }
    ok (true, "set up temporary fairshare database and tree");

    for (int pass = 0; pass < 2; pass++) {
        for (int i = 0; i < 4; i++)
            users[i]->set_fshare (values[pass][i]);

        rc = writer.write_acct_info (path, root);
        ok (rc == SQLITE_OK, "write doubles on pass %d: %s",
            pass + 1, writer.err_message ().c_str ());
        for (int i = 0; i < 4; i++) {
            ok (check_fshare (DB, users[i]->get_name (), expected[pass][i]),
                "%s: REAL fairshare rounded to 6 places on pass %d",
                users[i]->get_name ().c_str (), pass + 1);
        }
    }
done:
    if (DB && sqlite3_close (DB) != SQLITE_OK)
        cleaned = false;
    for (const auto &suffix : {"", "-wal", "-shm"}) {
        std::string filename = path + suffix;
        if (unlink (filename.c_str ()) < 0 && errno != ENOENT)
            cleaned = false;
    }
    ok (cleaned, "clean up temporary fairshare database");
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
    plan (16);

    test_double_binding ();

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
