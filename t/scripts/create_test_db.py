#!/usr/bin/env python3
###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
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
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import create_db as c


def edit_usage_col(conn, username, value):
    # edit value in accounting database
    conn.execute(
        "UPDATE association_table SET job_usage=? WHERE username=?",
        (
            value,
            username,
        ),
    )
    # commit changes
    conn.commit()


def main():
    if len(sys.argv) < 2:
        print("You must pass a path to the flux-accounting DB")
        sys.exit(-1)

    filename = sys.argv[1]
    c.create_db(filename)
    conn = sqlite3.connect(filename)

    b.add_bank(conn, bank="root", shares=1000)
    b.add_bank(conn, parent_bank="root", bank="account1", shares=1000)
    b.add_bank(conn, parent_bank="root", bank="account2", shares=100)
    b.add_bank(conn, parent_bank="root", bank="account3", shares=10)

    u.add_user(
        conn,
        username="leaf.1.1",
        uid="5011",
        bank="account1",
        shares="10000",
    )
    u.add_user(
        conn,
        username="leaf.1.2",
        uid="5012",
        bank="account1",
        shares="1000",
    )
    u.add_user(
        conn,
        username="leaf.1.3",
        uid="5013",
        bank="account1",
        shares="100000",
    )

    u.add_user(
        conn,
        username="leaf.2.1",
        uid="5021",
        bank="account2",
        shares="100000",
    )
    u.add_user(
        conn,
        username="leaf.2.2",
        uid="5022",
        bank="account2",
        shares="10000",
    )

    u.add_user(
        conn,
        username="leaf.3.1",
        uid="5031",
        bank="account3",
        shares="100",
    )
    u.add_user(
        conn,
        username="leaf.3.2",
        uid="5032",
        bank="account3",
        shares="10",
    )

    edit_usage_col(conn, "leaf.1.1", 100)
    edit_usage_col(conn, "leaf.1.2", 11)
    edit_usage_col(conn, "leaf.1.3", 10)

    edit_usage_col(conn, "leaf.2.1", 8)
    edit_usage_col(conn, "leaf.2.2", 3)

    edit_usage_col(conn, "leaf.3.1", 0)
    edit_usage_col(conn, "leaf.3.2", 1)

    conn.close()


if __name__ == "__main__":
    main()
