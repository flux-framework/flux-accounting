#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
from fluxacct.accounting import formatter as fmt

###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################
def view_factor(conn, factor, json_fmt=False, format_string=""):
    """
    View the integer weight for a particular priority factor in the plugin.

    Args:
        conn: the SQLite Connection object.
        factor: the name of the priority factor.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM priority_factor_weight_table WHERE factor=?", (factor,))
    formatter = fmt.PriorityFactorFormatter(cur, factor)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()
