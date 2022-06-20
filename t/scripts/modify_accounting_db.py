#!/usr/bin/env python3
###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sqlite3
import sys

import fluxacct.accounting
from fluxacct.accounting import create_db as c


def main():
    if len(sys.argv) < 2:
        print("You must pass a path to the flux-accounting DB")
        sys.exit(-1)

    filename = sys.argv[1]
    c.create_db(filename)
    conn = sqlite3.connect(filename)
    cur = conn.cursor()

    # add two new columns to the association_table in the flux-accounting DB
    cur.execute(
        "ALTER TABLE association_table ADD COLUMN organization text DEFAULT '' NOT NULL"
    )
    cur.execute(
        "ALTER TABLE association_table ADD COLUMN yrs_experience int(11) DEFAULT 0 NOT NULL"
    )

    # add a new table to the flux-accounting DB
    cur.execute(
        """CREATE TABLE IF NOT EXISTS organization (org_name        tinytext            NOT NULL,
                                                    org_number      int(11)  DEFAULT 0  NOT NULL,
                                                    num_members     int(11)  DEFAULT 0  NOT NULL,
                                                    org_description tinytext DEFAULT '' NOT NULL,
                                                    PRIMARY KEY (org_name));"""
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
