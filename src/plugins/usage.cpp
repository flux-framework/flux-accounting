/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include "usage.hpp"

#include "jj.hpp"
#include "job.hpp"

int Usage::get (const std::string &type) const
{
    return resource_count (resources, type);
}


Usage &Usage::operator+= (const Usage &rhs)
{
    jobs += rhs.jobs;
    for (const auto &entry : rhs.resources)
        resources[entry.first] += entry.second;
    return *this;
}


Usage &Usage::operator-= (const Usage &rhs)
{
    jobs -= rhs.jobs;
    for (const auto &entry : rhs.resources)
        resources[entry.first] -= entry.second;
    return *this;
}


Usage Usage::operator+ (const Usage &rhs) const
{
    Usage result = *this;

    result += rhs;
    return result;
}


void Usage::prune ()
{
    for (auto it = resources.begin (); it != resources.end ();) {
        if (it->second <= 0)
            it = resources.erase (it);
        else
            ++it;
    }
}


Usage Usage::of (const Job &job)
{
    Usage usage;

    usage.jobs = 1;
    usage.resources = job.resources;
    return usage;
}


Usage Usage::of (const jj_counts &counts)
{
    Usage usage;

    usage.jobs = 1;
    usage.resources = counts.counts;
    return usage;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
