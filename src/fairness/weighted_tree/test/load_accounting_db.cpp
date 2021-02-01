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

#include "src/fairness/weighted_tree/test/load_accounting_db.hpp"

using namespace Flux::accounting;

/*
bind_select_associations_stmt () will bind the required parameters to the
prepared SQL statement to find any and all associations under a bank.
*/
int bind_select_associations_stmt (int rc,
                                   const std::string &bank_name,
                                   sqlite3_stmt *b_select_associations_stmt)
{
    rc = sqlite3_bind_text (b_select_associations_stmt,
                            1,
                            bank_name.c_str (),
                            -1,
                            NULL);
    return rc;
}


/*
add_child_to_tree () constructs a weighted_tree_node_t object out of a
association's data retrieved from the SELECT SQL statement and adds it to the
weighted tree.
*/
void add_child_to_tree (std::shared_ptr<weighted_tree_node_t> parent_bank,
                        const std::string &username,
                        const std::string &user_shares,
                        const std::string &user_job_usage,
                        std::shared_ptr<weighted_tree_node_t> user_node,
                        std::shared_ptr<weighted_tree_node_t> node)
{
    // add user as a child of the node
    user_node = std::make_shared<weighted_tree_node_t> (
                                                parent_bank,
                                                username,
                                                true,
                                                std::stoll (user_shares),
                                                std::stoll (user_job_usage));
    node->add_child (user_node);
}

/*
aggregate_job_usage () takes the total usage from a leaf bank (i.e a bank with
associations in it) and adds it to the total usage of its parent bank and so on
up to the root bank.
*/
void aggregate_job_usage (std::shared_ptr<weighted_tree_node_t> node,
                          int leaf_bank_usage)
{
    // aggregate usage from user nodes up to their respective banks
    // and up to the root bank
    for (std::shared_ptr<weighted_tree_node_t> curr_ancestor = node;
         curr_ancestor != nullptr;
         curr_ancestor = curr_ancestor->get_parent ()) {

        curr_ancestor->set_usage (curr_ancestor->get_usage ()
                                  + leaf_bank_usage);
    }
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

It returns a shared pointer to the root of the tree.

If at any point during the depth-first search does an error code get returned
from any of the SQLite statements or an exception occurs, a nullptr is returned.
*/
std::shared_ptr<weighted_tree_node_t> get_sub_banks (
                            sqlite3 *DB,
                            const std::string &bank_name,
                            std::shared_ptr<weighted_tree_node_t> parent_bank,
                            sqlite3_stmt *b_select_shares_stmt,
                            sqlite3_stmt *b_select_sub_banks_stmt,
                            sqlite3_stmt *b_select_associations_stmt)
{

    std::shared_ptr<weighted_tree_node_t> node = nullptr;
    std::shared_ptr<weighted_tree_node_t> user_node = nullptr;
    std::shared_ptr<weighted_tree_node_t> root_ptr = nullptr;

    int rc = 0;
    int leaf_bank_usage = 0;

    // bind parameter to prepare SQL statement
    rc = sqlite3_bind_text (b_select_shares_stmt,
                            1,
                            bank_name.c_str (),
                            -1,
                            NULL);
    if (rc != SQLITE_OK) {
        std::cerr
            << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
        sqlite3_close (DB);

        return nullptr;
    }
    // execute SQL statement and store result
    rc = sqlite3_step (b_select_shares_stmt);
    if (rc == SQLITE_ERROR) {
        std::cerr
            << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
        sqlite3_close (DB);

        return nullptr;
    }

    std::string bank_shares = reinterpret_cast<char const *> (
        sqlite3_column_text (b_select_shares_stmt, 0));

    // initialize a weighted tree node
    try {
        node = std::make_shared<weighted_tree_node_t> (parent_bank,
                                                       bank_name,
                                                       false,
                                                       std::stoll (bank_shares),
                                                       0);
    }
    catch (const std::invalid_argument &ia) {
        std::cerr << "Invalid argument: " << ia.what() << std::endl;
        return nullptr;
    }
    catch (const std::out_of_range &oor) {
        std::cerr << "Out of range error: " << oor.what() << std::endl;
        return nullptr;
    }


    // if there is no parent bank, then the root pointer points to the root bank
    if (!parent_bank) {
        root_ptr = node;
    } else {
        parent_bank->add_child (node);
    }

    rc = sqlite3_bind_text (b_select_sub_banks_stmt,
                            1,
                            bank_name.c_str (),
                            -1,
                            NULL);
    if (rc != SQLITE_OK) {
        std::cerr
            << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
        sqlite3_close (DB);

        return nullptr;
    }
    rc = sqlite3_step (b_select_sub_banks_stmt);
    if (rc == SQLITE_ERROR) {
        std::cerr
            << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
        sqlite3_close (DB);

        return nullptr;
    }

    // vector of strings to hold sub banks
    std::vector<std::string> banks;

    // we've reached a bank with no sub banks, so add them to the tree
    // and tally up their usage to be aggregated up to their parent bank
    // and up to the root bank
    if (rc != SQLITE_ROW) {
        rc = bind_select_associations_stmt (rc,
                                            bank_name,
                                            b_select_associations_stmt);

        if (rc != SQLITE_OK) {
            std::cerr
                << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
            sqlite3_close (DB);

            return nullptr;
        }

        // execute SQL statement
        rc = sqlite3_step (b_select_associations_stmt);
        while (rc == SQLITE_ROW) {
            std::string username = reinterpret_cast<char const *> (
                sqlite3_column_text (b_select_associations_stmt, 0));
            std::string user_shares = reinterpret_cast<char const *> (
                sqlite3_column_text (b_select_associations_stmt, 1));
            std::string user_job_usage = reinterpret_cast<char const *> (
                sqlite3_column_text (b_select_associations_stmt, 3));

            try {
                // add user as a child of the node
                add_child_to_tree (parent_bank,
                                   username,
                                   user_shares,
                                   user_job_usage,
                                   user_node,
                                   node);

                // add single user's job usage to their bank's total job usage
                leaf_bank_usage += std::stoi (user_job_usage);
            }
            catch (const std::invalid_argument &ia) {
                std::cerr << "Invalid argument: " << ia.what() << std::endl;
                return nullptr;
            }
            catch (const std::out_of_range &oor) {
                std::cerr << "Out of range error: " << oor.what() << std::endl;
                return nullptr;
            }

            rc = sqlite3_step (b_select_associations_stmt);
        }
        if (rc == SQLITE_ERROR) {
            std::cerr
                << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
            sqlite3_close (DB);

            return nullptr;
        }

        aggregate_job_usage(node, leaf_bank_usage);
    } else {
        // otherwise, this bank has sub banks, so call this
        // function again with the first sub bank it found
        parent_bank = node;
        while (rc == SQLITE_ROW) {
            // execute SQL statement
            std::string bank = reinterpret_cast<char const *> (
                sqlite3_column_text (b_select_sub_banks_stmt, 0));
            banks.push_back (bank);
            rc = sqlite3_step (b_select_sub_banks_stmt);
        }
        if (rc == SQLITE_ERROR) {
            std::cerr
                << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
            sqlite3_close (DB);

            return nullptr;
        }
        for (const std::string &b : banks) {
            // reset the prepared statements back to their initial state and
            // clear their bindings
            rc = sqlite3_clear_bindings (b_select_associations_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }
            rc = sqlite3_reset (b_select_associations_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }
            rc = sqlite3_clear_bindings (b_select_sub_banks_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }
            rc = sqlite3_reset (b_select_sub_banks_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }
            rc = sqlite3_clear_bindings (b_select_shares_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }
            rc = sqlite3_reset (b_select_shares_stmt);
            if (rc != SQLITE_OK) {
                std::cerr << sqlite3_errmsg (DB) << std::endl;
                sqlite3_close (DB);

                return nullptr;
            }

            if (get_sub_banks (DB,
                               b,
                               parent_bank,
                               b_select_shares_stmt,
                               b_select_sub_banks_stmt,
                               b_select_associations_stmt) == nullptr) {
                std::cerr << "get_sub_banks () returned a nullptr" << std::endl;
                return nullptr;
            }
        }
    }
    return root_ptr;
}

std::shared_ptr<weighted_tree_node_t> load_accounting_db (
                                                    const std::string &path)
{
    // SQL statements to retrieve data from flux-accounting database
    sqlite3_stmt *b_select_root_bank_stmt = nullptr;
    sqlite3_stmt *b_select_shares_stmt = nullptr;
    sqlite3_stmt *b_select_sub_banks_stmt = nullptr;
    sqlite3_stmt *b_select_associations_stmt = nullptr;

    sqlite3 *DB = nullptr;
    int rc = 0;

    // open FluxAccounting DB in read-write mode; if it does not exist yet,
    // create a new database file
    rc = sqlite3_open_v2 (path.c_str (), &DB, SQLITE_OPEN_READWRITE, NULL);
    if (rc) {
        std::cerr << "error opening DB: " << sqlite3_errmsg (DB) << std::endl;
        return nullptr;
    }

    // SELECT statement to get the shares of the current bank
    std::string select_shares_stmt = "SELECT bank_table.shares "
                                     "FROM bank_table "
                                     "WHERE bank=?";
    rc = sqlite3_prepare_v2 (DB,
                             select_shares_stmt.c_str (),
                             -1,
                             &b_select_shares_stmt,
                             0);

    // SELECT statement to get all sub banks of the current bank
    std::string select_sub_banks_stmt = "SELECT bank_table.bank "
                                        "FROM bank_table "
                                        "WHERE parent_bank=?";
    rc = sqlite3_prepare_v2 (DB,
                             select_sub_banks_stmt.c_str (),
                             -1,
                             &b_select_sub_banks_stmt,
                             0);

    // SELECT statement to get all associations from a bank
    std::string select_associations_stmt = "SELECT association_table.username, "
                                           "association_table.shares, "
                                           "association_table.bank, "
                                           "association_table.job_usage "
                                           "FROM association_table "
                                           "WHERE association_table.bank=?";
    rc = sqlite3_prepare_v2 (DB,
                             select_associations_stmt.c_str (),
                             -1,
                             &b_select_associations_stmt,
                             0);

    // SELECT statement to get the root bank from the bank table
    std::string select_root_bank_stmt = "SELECT bank_table.bank "
                                        "FROM bank_table "
                                        "WHERE parent_bank=''";
    // compile SQL statement into byte code
    rc = sqlite3_prepare_v2 (DB,
                             select_root_bank_stmt.c_str(),
                             -1,
                             &b_select_root_bank_stmt,
                             0);
    if (rc != SQLITE_OK) {
        std::cerr
            << "Failed to fetch data: " << sqlite3_errmsg (DB) << std::endl;
        sqlite3_close (DB);

        return nullptr;
    }

    rc = sqlite3_step (b_select_root_bank_stmt);
    // store root bank name
    std::string root_bank;
    if (rc == SQLITE_ROW) {
        root_bank = reinterpret_cast<char const *> (
            sqlite3_column_text (b_select_root_bank_stmt, 0));
    }
    // otherwise, there is either no root bank or more than one
    // root bank; the program should exit
    else {
        std::cerr << "root bank not found, exiting" << std::endl;
        return nullptr;
    }

    // call recursive function
    std::shared_ptr<weighted_tree_node_t> root = nullptr;
    root = get_sub_banks (DB,
                          root_bank,
                          nullptr,
                          b_select_shares_stmt,
                          b_select_sub_banks_stmt,
                          b_select_associations_stmt);

    // destroy the prepared SQL statements
    sqlite3_finalize (b_select_root_bank_stmt);
    sqlite3_finalize (b_select_shares_stmt);
    sqlite3_finalize (b_select_sub_banks_stmt);
    sqlite3_finalize (b_select_associations_stmt);

    // close DB connection
    sqlite3_close (DB);

    return root;

}
