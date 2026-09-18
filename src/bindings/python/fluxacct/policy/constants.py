###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
PRIORITY_FACTORS = ["fairshare", "queue", "bank", "urgency"]
FSHARE_WEIGHT_DEFAULT = 100000
QUEUE_WEIGHT_DEFAULT = 10000
BANK_WEIGHT_DEFAULT = 0
URGENCY_WEIGHT_DEFAULT = 1000
INTEGER_MAX = 2147483647
