/************************************************************\
 * Copyright 2026 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

/* resource_quotas.cpp - track and limit concurrent resource usage
 *
 * flux-accounting ships two jobtap plugins with distinct policy sources.
 * The mf_priority plugin enforces what the flux-accounting database
 * defines. Those are per-association values managed with flux account
 * commands, such as multi-factor job priority, fair share, per-association
 * resource and job limits, and bank and queue permissions. This plugin
 * enforces what the TOML configuration defines. Those are site wide
 * concurrent resource quotas that apply uniformly, per user across banks
 * and eventually instance wide, for any resource type including custom
 * ones. The plugins are independent and either or both can be loaded. A
 * job must satisfy every policy from every loaded plugin.
 *
 * This plugin starts simple. It currently tracks per-user resource usage
 * for the resource types found in the jobspec of every running job.
 * Enforcement of configured quotas will build on this tracking.
 */

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
#include <flux/core.h>
#include <flux/jobtap.h>
#include <jansson.h>
}

static const struct flux_plugin_handler tab[] = {
    { 0 },
};

extern "C" int flux_plugin_init (flux_plugin_t *p)
{
    if (flux_plugin_register (p, "resource_quotas", tab) < 0)
        return -1;

    return 0;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
