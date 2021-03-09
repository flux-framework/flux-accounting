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

using namespace Flux::accounting;

namespace Flux {
namespace reader {

/*!  Base data reader class.
*/
class data_reader_base_t {
public:
    virtual ~data_reader_base_t () = default;

    std::shared_ptr<weighted_tree_node_t> load_accounting_info (
                                                    const std::string &path);

    /*! Return the error message string.
     */
    const std::string &err_message () const;

    /*! Clear the error message string.
     */
    void clear_err_message ();

protected:
    std::string m_err_msg = "";
};

} // namespace reader
} // namespace Flux
