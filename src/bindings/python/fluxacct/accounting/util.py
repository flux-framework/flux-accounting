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
import pwd


def get_uid(username):
    """
    Get the userid for a given username. If the userid cannot be found, just return
    the username.

    Args:
        username: The username.
    """
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return str(username)


def get_username(userid):
    """
    Get the username for a given userid. If the username cannot be found, just return
    the userid as a string.
    """
    try:
        return pwd.getpwuid(userid).pw_name
    except KeyError:
        return str(userid)
