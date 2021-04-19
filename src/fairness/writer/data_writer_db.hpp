/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#include <sqlite3.h>
#include <cerrno>

#include "src/fairness/weighted_tree/weighted_walk.hpp"
#include "src/fairness/writer/data_writer_base.hpp"

using namespace Flux::accounting;

namespace Flux {
namespace writer {

/*!  Base data writer class.
 */
class data_writer_db_t : public data_writer_base_t {
public:
    virtual ~data_writer_db_t () = default;

    /*! Write fairshare values from a weighted tree to a flux-accounting DB.
     *
     * \param path      path to a flux-accounting database
     * \param node      node of a weighted tree object
     * \return          integer return code indicating success or failure
     */
    int write_acct_info (const std::string &path,
                         std::shared_ptr<weighted_tree_node_t> node);

private:
    /*! Open a connection to a flux-accounting SQLite database.
     *
     * \param path      path to a flux-accounting database
     * \return          pointer to the database
     */
    sqlite3* open_db (const std::string &path);

    /*! Compile a SQL statement into byte code.
     *
     * \param DB        pointer to a SQLite database
     * \param s         the SQL statement to be compiled
     * \return          pointer to the compiled SQL statement
     */
    sqlite3_stmt* compile_stmt (sqlite3 *DB, const std::string &s);

    /*! Bind a parameter to a compiled SQL statement
     * \param DB        pointer to a SQLite database
     * \param cs        compiled SQL statement
     * \param index     the index to bind the parameter to
     * \param param     the parameter that is being binded to the statement
     * \return          pointer to compiled statement with bound parameter(s)
     */
    sqlite3_stmt* bind_param (sqlite3 *DB,
                              sqlite3_stmt *c_stmt,
                              int index,
                              const char *param);

    /*! Reset a SQL statement and clear it's bindings.
     *
     * \param DB        pointer to a SQLite database
     * \param s         the SQL statement to be reset
     * \return          integer return code indicating success or failure
     */
    int reset_and_clear_bindings (sqlite3 *DB, sqlite3_stmt *c_ud);

    /*! Update association_table with new fairshare values.
     *
     * \param DB        pointer to a SQLite database
     * \param c_ud      pointer to the compiled UPDATE statement
     * \param node      node of the weighted tree of the bank/user hierarchy
     * \return          integer return code indicating success or failure
     */
    int update_fairshare_values (sqlite3 *DB,
                                 sqlite3_stmt *c_ud,
                                 std::shared_ptr<weighted_tree_node_t> node);
};

} // namespace writer
} // namespace Flux
