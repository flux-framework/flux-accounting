/************************************************************\
 * Copyright 2020 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#ifndef WEIGHTED_TREE_LOAD_HPP
#define WEIGHTED_TREE_LOAD_HPP

#include "src/fairness/weighted_tree/weighted_walk.hpp"

int load_weighted_tree (
        const std::string &path,
        std::shared_ptr<Flux::accounting::weighted_tree_node_t> &rt_out);

#endif // WEIGHTED_TREE_LOAD_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
