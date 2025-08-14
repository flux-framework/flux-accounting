/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/
extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include "src/fairness/writer/data_writer_db.hpp"

using namespace Flux::accounting;
using namespace Flux::writer;

/******************************************************************************
 *                                                                            *
 *                         Private DB Writer API                              *
 *                                                                            *
 *****************************************************************************/

sqlite3* data_writer_db_t::open_db (const std::string &path)
{
    int rc;
    sqlite3 *DB = nullptr;
    char *errmsg = nullptr;

    // open flux-accounting DB in read-write mode
    rc = sqlite3_open_v2 (path.c_str (), &DB, SQLITE_OPEN_READWRITE, NULL);
    if (rc != SQLITE_OK) {
        m_err_msg = "error opening DB: " + std::string (sqlite3_errmsg (DB));
        errno = EIO;

        return nullptr;
    }

    rc = sqlite3_busy_timeout (DB, 30000);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string ("sqlite3_busy_timeout failed: ")
                    + sqlite3_errmsg (DB);
        goto error;
    }

    // decouple the readers and writer
    rc = sqlite3_exec (DB,
                       "PRAGMA journal_mode=WAL;",
                       nullptr,
                       nullptr,
                       &errmsg);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string("PRAGMA journal_mode=WAL failed: ")
                    + (errmsg ? errmsg : sqlite3_errmsg (DB));
        goto error;
    }
    sqlite3_free (errmsg);
    errmsg = nullptr;

    // reduce fsync cost while keeping durability reasonable for WAL
    rc = sqlite3_exec (DB,
                       "PRAGMA synchronous=NORMAL;",
                       nullptr,
                       nullptr,
                       &errmsg);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string ("PRAGMA synchronous=NORMAL failed: ")
                    + (errmsg ? errmsg : sqlite3_errmsg (DB));
        goto error;
    }
    sqlite3_free (errmsg);
    errmsg = nullptr;

    // keep temp objects in memory to avoid extra file churn
    rc = sqlite3_exec (DB,
                       "PRAGMA temp_store=MEMORY;",
                       nullptr,
                       nullptr,
                       &errmsg);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string("PRAGMA temp_store=MEMORY failed: ")
                    + (errmsg ? errmsg : sqlite3_errmsg (DB));
        goto error;
    }
    sqlite3_free (errmsg);
    errmsg = nullptr;

    return DB;
error:
    if (errmsg) {
        sqlite3_free (errmsg);
        errmsg = nullptr;
    }
    if (DB) {
        sqlite3_close (DB);
        DB = nullptr;
    }
    errno = EIO;
    return nullptr;
}


sqlite3_stmt* data_writer_db_t::compile_stmt (sqlite3 *DB, const std::string &s)
{
    int rc;
    sqlite3_stmt *c_stmt = nullptr;

    // compile SQL statement
    rc = sqlite3_prepare_v2 (DB, s.c_str (), -1, &c_stmt, 0);
    if (rc != SQLITE_OK) {
        m_err_msg = sqlite3_errmsg (DB);
        errno = EINVAL;

        return nullptr;
    }

    return c_stmt;
}


sqlite3_stmt* data_writer_db_t::bind_param (sqlite3 *DB,
                                            sqlite3_stmt *c_stmt,
                                            int index,
                                            const char *param)
{
    int rc;

    // bind parameter to compiled SQL statement
    rc = sqlite3_bind_text (c_stmt, index, param, -1, NULL);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string (sqlite3_errmsg (DB)) + "\n";
        errno = EINVAL;

        return nullptr;
    }

    return c_stmt;
}


int data_writer_db_t::reset_and_clear_bindings (sqlite3 *DB, sqlite3_stmt *c_ud)
{
    int rc;

    rc = sqlite3_clear_bindings (c_ud);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string (sqlite3_errmsg (DB)) + "\n";

        return rc;
    }
    rc = sqlite3_reset (c_ud);
    if (rc != SQLITE_OK) {
        m_err_msg = std::string (sqlite3_errmsg (DB)) + "\n";

        return rc;
    }

    return rc;
}


int data_writer_db_t::update_fairshare_values (
                                    sqlite3 *DB,
                                    sqlite3_stmt *c_ud,
                                    std::shared_ptr<weighted_tree_node_t> node)
{
    int rc;
    const char *fshare, *username, *bank;

    if (node->is_user ()) {
        // get parameters for UPDATE statement
        fshare = std::to_string (node->get_fshare ()).c_str ();
        username = node->get_name ().c_str ();
        bank = node->get_parent ()->get_name ().c_str ();

        // bind parameters to compiled SQL statement
        c_ud = bind_param (DB, c_ud, 1, fshare);
        if (c_ud == nullptr)
            return -1;

        c_ud = bind_param (DB, c_ud, 2, username);
        if (c_ud == nullptr)
            return -1;

        c_ud = bind_param (DB, c_ud, 3, bank);
        if (c_ud == nullptr)
            return -1;

        // execute UPDATE statement
        rc = sqlite3_step (c_ud);
        if (rc == SQLITE_ERROR) {
            m_err_msg += "Unable to update association_table\n";
            errno = EINVAL;

            return rc;
        }
    }

    rc = reset_and_clear_bindings (DB, c_ud);
    if (rc != SQLITE_OK) {
        errno = EINVAL;

        return -1;
    }

    // recur on subtree
    for (int i = 0; i < node->get_num_children (); i++) {
        update_fairshare_values (DB, c_ud, node->get_child (i));
    }

    return rc;
}


/******************************************************************************
 *                                                                            *
 *                         Public DB Writer API                               *
 *                                                                            *
 *****************************************************************************/

int data_writer_db_t::write_acct_info (
                                    const std::string &path,
                                    std::shared_ptr<weighted_tree_node_t> node)
{
    int rc;
    sqlite3 *DB = nullptr;
    std::string ud;
    sqlite3_stmt *c_ud = nullptr;

    DB = open_db (path.c_str ());
    if (DB == nullptr) {
        errno = EINVAL;

        return -1;
    }

    ud = "UPDATE association_table SET fairshare=? WHERE username=? AND bank=?";

    c_ud = compile_stmt (DB, ud);
    if (c_ud == nullptr)
        return -1;

    rc = update_fairshare_values (DB, c_ud, node);

    // destroy prepared statement
    rc = sqlite3_finalize (c_ud);
    if (rc != SQLITE_OK) {
        m_err_msg = "Failed to delete prepared statement";

        return rc;
    }

    // close DB connection
    sqlite3_close (DB);

    return rc;
}
