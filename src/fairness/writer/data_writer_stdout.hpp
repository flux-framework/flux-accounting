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
#include "src/fairness/reader/data_reader_db.hpp"
#include "src/fairness/writer/data_writer_base.hpp"

using namespace Flux::accounting;

namespace Flux {
namespace writer {

/*!  Base data writer class.
 */
class data_writer_stdout_t : public data_writer_base_t {
public:
    data_writer_stdout_t (std::string indent = "",
                          bool parsable = false,
                          std::string delimiter = "")
    {
        m_indent = indent;
        m_parsable = parsable;
        m_delimiter = delimiter;
    }
    virtual ~data_writer_stdout_t () = default;

    /*! Write fairshare values from a weighted tree.
     *
     * \param path          path to a flux-accounting database
     * \param node          node of the weighted tree of the bank/user hierarchy
     */
    int write_acct_info (const std::string &path,
                         std::shared_ptr<weighted_tree_node_t> node);

private:
    std::string m_indent = "";
    bool m_parsable = false;
    std::string m_delimiter = "";

    /*! Print flux-accounting information with a custom delimiter.
     *
     * \param delimiter     custom delimiter for output
     */
    void print_csv_header (const std::string& delimiter="|");

    /*! Bind a parameter to a compiled SQL statement
     *
     * \param node          node of the weighted tree of the bank/user hierarchy
     * \param indent        level of indent in printing out the hierarchy
     * \param delimiter     custom delimiter for output
     */
     void print_csv (std::shared_ptr<weighted_tree_node_t> node,
                     const std::string& indent,
                     const std::string& delimiter="|");

    /*! Print the header in a nice format.
     *
     */
    void pretty_print_header ();

    /*! Print the user/bank hierarchy in a nice format.
     *
     * \param node      node of the weighted tree of the bank/user hierarchy
     * \param indent    level of indent in printing out the hierarchy
     */
     void pretty_print (std::shared_ptr<weighted_tree_node_t> node,
                        const std::string& indent);
};

} // namespace writer
} // namespace Flux
