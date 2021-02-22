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

#include <cstdlib>
#include <iostream>
#include <sqlite3.h>
#include <tuple>
#include <vector>
#include <cerrno>

#include "src/fairness/reader/data_reader_db.hpp"

using namespace Flux::accounting;

/*
delete_prepared_statement () will delete the prepared SQL statements.
*/
int delete_prepared_statements (sqlite3_stmt *c_root_bank,
                                sqlite3_stmt *c_shrs,
                                sqlite3_stmt *c_sub_banks,
                                sqlite3_stmt *c_assoc)
{
    int rc = 0;
    std::vector<sqlite3_stmt*> stmts;

    stmts.push_back(c_root_bank);
    stmts.push_back(c_shrs);
    stmts.push_back(c_sub_banks);
    stmts.push_back(c_assoc);

    for (sqlite3_stmt *stmt : stmts) {
        rc = sqlite3_finalize (stmt);
        if (rc != SQLITE_OK) {
            std::cerr << "Failed to delete prepared statement" << std::endl;

            return rc;
        }
    }

    return rc;
}


/*
add_assoc () constructs a weighted_tree_node_t object out of a
association's data and adds it to the weighted tree.
*/
int add_assoc (const std::string &username,
               const std::string &shrs,
               const std::string &usg,
               std::shared_ptr<weighted_tree_node_t> &node)
{
    // add user as a child of the node
    auto user_node = std::make_shared<weighted_tree_node_t> (node,
                                                             username,
                                                             true,
                                                             std::stoll (shrs),
                                                             std::stoll (usg));
    return node->add_child (user_node);
}


/*
aggregate_job_usage () takes the total usage from a leaf bank (i.e a bank with
associations in it) and adds it to the total usage of its parent bank and so on
up to the root bank.
*/
void aggregate_job_usage (std::shared_ptr<weighted_tree_node_t> node,
                          int bank_usage)
{
    // aggregate usage from user nodes up to their respective banks
    // and up to the root bank
    for (std::shared_ptr<weighted_tree_node_t> curr_ancestor = node;
         curr_ancestor != nullptr;
         curr_ancestor = curr_ancestor->get_parent ()) {

        curr_ancestor->set_usage (curr_ancestor->get_usage () + bank_usage);
    }
}


/*
reset_and_clear_bindings () will reset the compiled SQL statements.
*/
int reset_and_clear_bindings (sqlite3 *DB,
                              sqlite3_stmt *c_assoc,
                              sqlite3_stmt *c_sub_banks,
                              sqlite3_stmt *c_shrs)
{
    int rc = 0;
    std::vector<sqlite3_stmt*> stmts;

    stmts.push_back(c_assoc);
    stmts.push_back(c_sub_banks);
    stmts.push_back(c_shrs);

    for (sqlite3_stmt *stmt : stmts) {
        rc = sqlite3_clear_bindings (stmt);
        if (rc != SQLITE_OK) {
            std::cerr << sqlite3_errmsg (DB) << std::endl;

            return rc;
        }
        rc = sqlite3_reset (stmt);
        if (rc != SQLITE_OK) {
            std::cerr << sqlite3_errmsg (DB) << std::endl;

            return rc;
        }
    }

    return rc;
}


/*
get_sub_banks () performs a depth-first search of the flux-accounting database,
starting at the root bank and descending down into its sub banks all the way
down to each bank's associations. It takes a handle to the SQLite database, the
name of the current bank, its parent bank (unless it is the root bank), and a
couple of SELECT SQL queries to fetch data from the database as input.

It will construct a weighted_tree_node_t object of every bank and association
it comes across, adding it to a tree.

It will also tally up job usage values up from each association back up to its
respctive parent bank and up to the root bank as it traverses.

It returns a shared pointer to the root of the subtree.

If at any point during the depth-first search does an error code get returned
from any of the SQLite statements or an exception occurs, a nullptr is returned.
*/
std::shared_ptr<weighted_tree_node_t> get_sub_banks (
                            sqlite3 *DB,
                            const std::string &bank_name,
                            std::shared_ptr<weighted_tree_node_t> parent_bank,
                            sqlite3_stmt *c_shrs,
                            sqlite3_stmt *c_sub_banks,
                            sqlite3_stmt *c_assoc)
{

    std::shared_ptr<weighted_tree_node_t> node = nullptr;

    int rc = 0;

    // vector of strings to hold sub banks
    std::vector<std::string> banks;

    // bind parameter to prepare SQL statement
    rc = sqlite3_bind_text (c_shrs, 1, bank_name.c_str (), -1, NULL);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;

        return nullptr;
    }
    rc = sqlite3_step (c_shrs);
    if (rc != SQLITE_ROW) {
        std::cerr << "Unable to fetch data" << std::endl;
        errno = EPROTO;

        return nullptr;
    }

    std::string bank_shrs = reinterpret_cast<char const *> (
        sqlite3_column_text (c_shrs, 0));

    // initialize a weighted tree node
    try {
        node = std::make_shared<weighted_tree_node_t> (parent_bank,
                                                       bank_name,
                                                       false,
                                                       std::stoll (bank_shrs),
                                                       0);
    }
    catch (const std::invalid_argument &ia) {
        std::cerr << "Invalid argument: " << ia.what() << std::endl;
        errno = EINVAL;

        return nullptr;
    }
    catch (const std::out_of_range &oor) {
        std::cerr << "Out of range error: " << oor.what() << std::endl;
        errno = EINVAL;

        return nullptr;
    }

    // if there is no parent bank, then the node being added is the root bank
    if (parent_bank)
        parent_bank->add_child (node);

    rc = sqlite3_bind_text (c_sub_banks, 1, bank_name.c_str (), -1, NULL);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;

        return nullptr;
    }
    rc = sqlite3_step (c_sub_banks);
    if (rc == SQLITE_ERROR) {
        std::cerr << "Unable to fetch data" << std::endl;
        errno = EPROTO;

        return nullptr;
    }

    // we've reached a bank with no sub banks, so add associations to the tree
    if (rc != SQLITE_ROW) {
        int bank_usg = 0;

        rc = sqlite3_bind_text (c_assoc, 1, bank_name.c_str (), -1, NULL);
        if (rc != SQLITE_OK) {
            std::cerr << sqlite3_errmsg (DB) << std::endl;
            errno = EPROTO;

            return nullptr;
        }

        // execute SQL statement
        rc = sqlite3_step (c_assoc);
        while (rc == SQLITE_ROW) {
            std::string username = reinterpret_cast<char const *> (
                sqlite3_column_text (c_assoc, 0));
            std::string shrs = reinterpret_cast<char const *> (
                sqlite3_column_text (c_assoc, 1));
            std::string usage = reinterpret_cast<char const *> (
                sqlite3_column_text (c_assoc, 3));

            try {
                // add association as a child of the node
                if (add_assoc (username, shrs, usage, node) < 0) {
                    std::cerr << "Failed to add association" << std::endl;
                    errno = EPROTO;

                    return nullptr;
                }

                bank_usg += std::stoi (usage);
            }
            catch (const std::invalid_argument &ia) {
                std::cerr << "Invalid argument: " << ia.what() << std::endl;
                errno = EINVAL;

                return nullptr;
            }
            catch (const std::out_of_range &oor) {
                std::cerr << "Out of range error: " << oor.what() << std::endl;
                errno = EINVAL;

                return nullptr;
            }

            rc = sqlite3_step (c_assoc);
        }
        if (rc == SQLITE_ERROR) {
            std::cerr << "Unable to fetch data" << std::endl;
            errno = EPROTO;

            return nullptr;
        }

        aggregate_job_usage (node, bank_usg);
    } else {
        // otherwise, this bank has sub banks, so call this
        // function again with the first sub bank it found
        parent_bank = node;
        while (rc == SQLITE_ROW) {
            std::string bank = reinterpret_cast<char const *> (
                sqlite3_column_text (c_sub_banks, 0));

            banks.push_back (bank);
            rc = sqlite3_step (c_sub_banks);
        }
        if (rc == SQLITE_ERROR) {
            std::cerr << "Unable to fetch data" << std::endl;
            errno = EPROTO;

            return nullptr;
        }
        for (const std::string &b : banks) {
            // reset the prepared statements back to their initial state and
            // clear their bindings
            rc = reset_and_clear_bindings (DB, c_assoc, c_sub_banks, c_shrs);
            if (rc != SQLITE_OK) {
                errno = EPROTO;

                return nullptr;
            }

            if (get_sub_banks (DB,
                               b,
                               parent_bank,
                               c_shrs,
                               c_sub_banks,
                               c_assoc) == nullptr) {
                std::cerr << "get_sub_banks () returned a nullptr" << std::endl;
                return nullptr;
            }
        }
    }
    return node;
}

std::shared_ptr<weighted_tree_node_t> load_accounting_db (
                                                    const std::string &path)
{
    // SQL statements to retrieve data from flux-accounting database
    std::string s_shrs, s_sub_banks, s_assoc, s_root_bank;
    sqlite3_stmt *c_root_bank = nullptr;
    sqlite3_stmt *c_shrs = nullptr;
    sqlite3_stmt *c_sub_banks = nullptr;
    sqlite3_stmt *c_assoc = nullptr;

    sqlite3 *DB = nullptr;
    int rc = 0;

    std::string root_bank;
    std::shared_ptr<weighted_tree_node_t> root = nullptr;

    // open flux-accounting DB in read-write mode
    rc = sqlite3_open_v2 (path.c_str (), &DB, SQLITE_OPEN_READWRITE, NULL);
    if (rc != SQLITE_OK) {
        std::cerr << "error opening DB: " << sqlite3_errmsg (DB) << std::endl;
        errno = EIO;

        return nullptr;
    }

    s_shrs = "SELECT bank_table.shares FROM bank_table WHERE bank=?";

    s_sub_banks = "SELECT bank_table.bank FROM bank_table WHERE parent_bank=?";

    s_assoc = "SELECT association_table.username, association_table.shares, "
              "association_table.bank, association_table.job_usage "
              "FROM association_table WHERE association_table.bank=?";

    s_root_bank = "SELECT bank_table.bank FROM bank_table WHERE parent_bank=''";

    // compile SELECT statements into byte code
    rc = sqlite3_prepare_v2 (DB, s_shrs.c_str (), -1, &c_shrs, 0);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;
        goto done;
    }

    rc = sqlite3_prepare_v2 (DB, s_sub_banks.c_str (), -1, &c_sub_banks, 0);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;
        goto done;
    }

    rc = sqlite3_prepare_v2 (DB, s_assoc.c_str (), -1, &c_assoc, 0);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;
        goto done;
    }

    rc = sqlite3_prepare_v2 (DB, s_root_bank.c_str (), -1, &c_root_bank, 0);
    if (rc != SQLITE_OK) {
        std::cerr << sqlite3_errmsg (DB) << std::endl;
        errno = EPROTO;
        goto done;
    }

    // fetch root bank from flux-accounting database
    rc = sqlite3_step (c_root_bank);
    if (rc == SQLITE_ROW) {
        root_bank = reinterpret_cast<char const *> (
            sqlite3_column_text (c_root_bank, 0));
    } else {
        // otherwise, there is either no root bank or more than one
        // root bank; the program should return nullptr
        std::cerr << "root bank not found, exiting" << std::endl;
        goto done;
    }

    // call recursive function
    root = get_sub_banks (DB, root_bank, nullptr, c_shrs, c_sub_banks, c_assoc);
    if (root == nullptr)
        goto done;

done:
    // close DB connection
    sqlite3_close (DB);

    // destroy the prepared SQL statements
    rc = delete_prepared_statements (c_root_bank, c_shrs, c_sub_banks, c_assoc);
    if (rc != SQLITE_OK) {
        errno = EPROTO;

        return nullptr;
    }

    return root;

}
