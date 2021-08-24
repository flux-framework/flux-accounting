/************************************************************\
 * Copyright 2021 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/
#include "src/fairness/writer/data_writer_base.hpp"

using namespace Flux::writer;

/******************************************************************************
 *                                                                            *
 *                         Public Base Reader API                             *
 *                                                                            *
 *****************************************************************************/
const std::string &data_writer_base_t::err_message () const
{
    return m_err_msg;
}

void data_writer_base_t::clear_err_message ()
{
    m_err_msg = "";
}
