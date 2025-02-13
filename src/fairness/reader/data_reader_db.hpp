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
#include "src/fairness/reader/data_reader_base.hpp"

using namespace Flux::accounting;

namespace Flux {
namespace reader {

/*!  Base data reader class.
 */
class data_reader_db_t : public data_reader_base_t {
public:
    virtual ~data_reader_db_t () = default;

    /*! Load flux-accounting database information into weighted tree.
     *
     * \param path      path to a flux-accounting SQLite database
     * \return          pointer to the root of the weighted tree
     */
    std::shared_ptr<weighted_tree_node_t> load_accounting_db (
                                                    const std::string &path);

private:
    int delete_prepared_statements (sqlite3_stmt *c_root_bank,
                                    sqlite3_stmt *c_shrs,
                                    sqlite3_stmt *c_sub_banks,
                                    sqlite3_stmt *c_assoc);

    int add_assoc (const std::string &username,
                   uint64_t shrs,
                   double usg,
                   double fshare,
                   std::shared_ptr<weighted_tree_node_t> &node);

    void aggregate_job_usage (std::shared_ptr<weighted_tree_node_t> node,
                              int bank_usage);

    int reset_and_clear_bindings (sqlite3 *DB,
                                  sqlite3_stmt *c_assoc,
                                  sqlite3_stmt *c_sub_banks,
                                  sqlite3_stmt *c_shrs);

    std::shared_ptr<weighted_tree_node_t> get_sub_banks (
                            sqlite3 *DB,
                            const std::string &bank_name,
                            std::shared_ptr<weighted_tree_node_t> parent_bank,
                            sqlite3_stmt *c_shrs,
                            sqlite3_stmt *c_sub_banks,
                            sqlite3_stmt *c_assoc);
};

} // namespace reader
} // namespace Flux
