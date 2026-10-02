/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

#ifndef USAGE_HPP
#define USAGE_HPP

#include <map>
#include <string>

class Job;
struct jj_counts;

// Generic count of jobs and resources consumed by one or more jobs.
struct Usage {
    int jobs = 0;
    std::map<std::string, int> resources;

    int get (const std::string &type) const;
    Usage &operator+= (const Usage &rhs);
    Usage &operator-= (const Usage &rhs);
    Usage operator+ (const Usage &rhs) const;
    void prune ();

    static Usage of (const Job &job);
    static Usage of (const jj_counts &counts);
};

#endif // USAGE_HPP

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
