#!/usr/bin/env python3
"""
module for calculating a user's fairshare value when
submitting jobs
"""

import sys
import sqlite3


def check_user_id(usr_id):

    # ensure that id specified is a valid int
    if isinstance(usr_id, int):
        return "user id specified: " + str(usr_id)
    else:
        print("user id specified is not an integer")
        print("aborting...")
        return -1


def fetch_usr_data(usr_id):
    # check that user id is in user table
    # open connection to database
    print("Opening JobCompletion DB...")
    conn = sqlite3.connect("JobCompletion.db")
    print("Opened JobCompletion DB successfully\n")

    # check if user exists in table
    print("obtaining user data from database... ")
    sel_statement = "SELECT * FROM users_assoc_table WHERE userid=" + str(usr_id)
    cursor = conn.cursor()
    cursor.execute(sel_statement)
    records = cursor.fetchall()

    if len(records) == 0:
        return "user not found in database"
    else:
        for col in records:
            usr_acct_info = {"user_id": col[0], "acct": col[1], "shares": col[2]}

        print("\tuserid: ", usr_acct_info["user_id"])
        print("\tacct: ", usr_acct_info["acct"])
        print("\tshares: ", usr_acct_info["shares"])
        return usr_acct_info


print(fetch_usr_data(12345))
