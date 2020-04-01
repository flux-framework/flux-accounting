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


def create_db():
    # open connection to database
    print("Creating JobCompletion DB...")
    conn = sqlite3.connect("JobCompletion.db")
    print("Created JobCompletion DB sucessfully")

    # create table in DB
    print("Creating inactive table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS inactive (
                t_submit   text NOT NULL,
                name       text NOT NULL,
                t_run      text NOT NULL,
                t_cleanup  text NOT NULL,
                userid     text NOT NULL,
                ntasks     text NOT NULL,
                t_inactive text NOT NULL,
                t_depend   text NOT NULL,
                priority   text NOT NULL,
                state      text NOT NULL,
                t_sched    text NOT NULL,
                id         text PRIMARY KEY
            );"""
    )
    print("Created table successfully")

    # create user table in DB
    print("Creating user table in DB...")
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS users_assoc_table (
                userid     text PRIMARY KEY,
                acct       text NOT NULL,
                shares     text NOT NULL
            );"""
    )
    print("Created table successfully")


def main():
    create_db()


main()
