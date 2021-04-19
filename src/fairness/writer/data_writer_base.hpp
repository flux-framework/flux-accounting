/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

using namespace Flux::accounting;

namespace Flux {
namespace writer {

/*!  Base data writer class.
*/
class data_writer_base_t {
public:
    virtual ~data_writer_base_t () = default;

    /*! Write fairshare values from a weighted tree.
     *
     * \param path      end destination to write accounting info to
     * \param node      node of a weighted tree object
     */
    int write_acct_info (const std::string &path,
                         std::shared_ptr<weighted_tree_node_t> node);

    /*! Return the error message string.
     */
    const std::string &err_message () const;

    /*! Clear the error message string.
     */
    void clear_err_message ();

protected:
    std::string m_err_msg = "";
};

} // namespace writer
} // namespace Flux
