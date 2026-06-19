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
import os
import pwd

import fluxacct.accounting
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import util
from fluxacct.accounting.util import with_cursor

###############################################################
#                                                             #
#                      Helper Functions                       #
#                                                             #
###############################################################
def validate_parent_bank(cur, parent_bank):
    try:
        cur.execute("SELECT shares FROM bank_table WHERE bank=?", (parent_bank,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(parent_bank)

        return 0
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")


def bank_is_active(cur, bank, parent_bank):
    """Check if the bank already exists and is active."""
    cur.execute(
        "SELECT active FROM bank_table WHERE bank=? AND parent_bank=?",
        (
            bank,
            parent_bank,
        ),
    )
    is_active = cur.fetchall()
    if len(is_active) > 0 and is_active[0][0] == 1:
        return True

    return False


def check_if_bank_disabled(cur, bank, parent_bank):
    """
    Check if the bank already exists but was disabled first. If so, just
    update the 'active' column in the already existing row.
    """
    cur.execute(
        "SELECT * FROM bank_table WHERE bank=? AND parent_bank=?",
        (bank, parent_bank),
    )
    result = cur.fetchall()
    if len(result) == 1:
        return True

    return False


def reactivate_bank(conn, cur, bank, parent_bank):
    """Re-enable the bank by setting 'active' to 1."""
    cur.execute(
        "UPDATE bank_table SET active=1 WHERE bank=? AND parent_bank=?",
        (
            bank,
            parent_bank,
        ),
    )
    conn.commit()


###############################################################
#                                                             #
#                   Subcommand Functions                      #
#                                                             #
###############################################################


def _build_sharetree(cur):
    """Build hierarchical sharetree with normalized shares and usage."""
    sharetree = {}

    # get root bank
    cur.execute("SELECT bank, shares, job_usage FROM bank_table WHERE parent_bank=''")
    root = cur.fetchone()
    if not root:
        raise ValueError("No root bank found in bank_table")

    root_bank_name, root_shares, root_usage = root
    fqname = f"/{root_bank_name}/"
    sharetree[fqname] = {
        "name": fqname,
        "shortname": root_bank_name,
        "parent": "",
        "children": [],
        "shares": root_shares,
        "nshares": 1.0,
        "usage": root_usage,
        "nusage": 1.0,
        "priority": float("nan"),
        "fshare": float("inf"),
        "depth": 0,
        "isuser": False,
    }

    # recursively build tree
    def build_tree(parent_name, parent_fqname, depth):
        # get sub-banks
        cur.execute(
            "SELECT bank, shares, job_usage FROM bank_table "
            "WHERE parent_bank=? ORDER BY bank",
            (parent_name,),
        )
        for row in cur.fetchall():
            bank_name, shares, usage = row
            child_fqname = f"{parent_fqname}{bank_name}/"
            sharetree[parent_fqname]["children"].append(bank_name)
            sharetree[child_fqname] = {
                "name": child_fqname,
                "shortname": bank_name,
                "parent": parent_fqname,
                "children": [],
                "shares": shares,
                "nshares": 0.0,
                "usage": usage,
                "nusage": 0.0,
                "priority": float("nan"),
                "fshare": float("nan"),
                "depth": depth,
                "isuser": False,
            }
            build_tree(bank_name, child_fqname, depth + 1)

        # get users under this bank
        cur.execute(
            """SELECT username, shares, job_usage, fairshare
               FROM association_table WHERE bank=? ORDER BY username""",
            (parent_name,),
        )
        for row in cur.fetchall():
            username, shares, usage, fshare = row
            user_fqname = f"{parent_fqname}{username}/"
            sharetree[parent_fqname]["children"].append(username)
            sharetree[user_fqname] = {
                "name": user_fqname,
                "shortname": username,
                "parent": parent_fqname,
                "children": [],
                "shares": shares,
                "nshares": 0.0,
                "usage": usage,
                "nusage": 0.0,
                "priority": float("nan"),
                "fshare": fshare,
                "depth": depth,
                "isuser": True,
            }

    build_tree(root_bank_name, fqname, 1)

    # calculate normalized shares and usage
    root_node = sharetree[f"/{root_bank_name}/"]

    # calculate normalized shares
    nodes_by_depth = sorted(sharetree.values(), key=lambda n: n["depth"])
    for node in nodes_by_depth:
        if node["shortname"] == root_bank_name or not node["parent"]:
            continue

        parent = sharetree[node["parent"]]
        sibling_shares = sum(
            sharetree[f"{node['parent']}{child}/"]["shares"]
            for child in parent["children"]
            if sharetree[f"{node['parent']}{child}/"]["isuser"] == node["isuser"]
        )
        if sibling_shares > 0:
            fraction = node["shares"] / sibling_shares
            node["nshares"] = fraction * parent["nshares"]

    # calculate normalized usage
    if root_node["usage"] > 0:
        for node in sharetree.values():
            node["nusage"] = node["usage"] / root_node["usage"]

    return sharetree


@with_cursor
def add_bank(
    conn, cur, bank, shares, parent_bank="", priority=0.0, ignore_older_than=0
):
    if parent_bank == "":
        # a root bank is trying to be added; check that one does not already exist
        cur.execute("SELECT * FROM bank_table WHERE parent_bank=''")
        if len(cur.fetchall()) > 0:
            raise ValueError(f"bank_table already has a root bank")

    # if the parent bank is not "", that means the bank trying
    # to be added wants to be placed under an existing parent bank
    try:
        if parent_bank != "":
            validate_parent_bank(cur, parent_bank)
    except ValueError as bad_parent_bank:
        raise ValueError(f"parent bank {bad_parent_bank} not found in bank table")

    # check that there exist no associations currently under the parent bank
    cur.execute("SELECT * FROM association_table WHERE bank=?", (parent_bank,))
    associations = cur.fetchall()
    if len(associations) > 0:
        # there is at least one association already under the parent bank; raise an error
        raise ValueError(
            "banks cannot be added to a bank that currently has associations in it"
        )

    # check if bank already exists and is active in bank_table; if so, raise
    # a sqlite3.IntegrityError
    if bank_is_active(cur, bank, parent_bank):
        raise sqlite3.IntegrityError(f"bank {bank} already exists in bank_table")

    # if true, bank already exists in table but is not
    # active, so re-activate the bank and return
    if check_if_bank_disabled(cur, bank, parent_bank):
        reactivate_bank(conn, cur, bank, parent_bank)
        return 0

    # convert to a timestamp
    ignore_older_than = util.parse_timestamp(ignore_older_than)

    # insert the bank values into the database
    try:
        cur.execute(
            """
            INSERT INTO bank_table (
                bank,
                parent_bank,
                shares,
                priority,
                ignore_older_than
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (bank, parent_bank, shares, priority, ignore_older_than),
        )
        # commit changes
        conn.commit()

        return 0
    # make sure entry is unique
    except sqlite3.IntegrityError:
        raise sqlite3.IntegrityError(f"bank {bank} already exists in bank_table")


@with_cursor
def view_bank(
    conn,
    cur,
    bank,
    tree=False,
    users=False,
    parsable=False,
    cols=None,
    format_string="",
    concise=False,
    active=False,
):
    if tree and cols is not None:
        # tree format cannot be combined with custom formatting, so raise an Exception
        raise ValueError(f"--tree option does not support custom formatting")
    if parsable and not tree:
        # --parsable can only be called with --tree, so raise an Exception
        raise ValueError(f"-P/--parsable can only be passed with -t/--tree")

    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.BANK_TABLE

    sql.validate_columns(cols, fluxacct.accounting.BANK_TABLE)
    # construct SELECT statement
    select_stmt = f"SELECT {', '.join(cols)} FROM bank_table WHERE bank=?"
    cur.execute(select_stmt, (bank,))

    # initialize BankFormatter object
    formatter = fmt.BankFormatter(cur, bank)

    if format_string != "":
        return formatter.as_format_string(format_string)
    if tree:
        if parsable:
            return formatter.as_parsable_tree(bank, concise, active)
        return formatter.as_tree(concise, active)
    if users:
        return formatter.with_users(bank, concise, active)
    return formatter.as_json()


@with_cursor
def delete_bank(conn, cur, bank, force=False):
    """
    Deactivate a bank row in the bank_table by setting its 'active' status to 0.
    If force=True, actually remove the bank row from the bank_table. If the bank contains
    multiple sub-banks and associations, either disable or actually remove those rows as
    well.

    Args:
        conn: The SQLite Connection object
        bank: the name of the bank
        force: an option to actually remove the row from the bank_table instead of
            just setting the 'active' column to 0.
    """
    if force:
        sql_stmt = "DELETE FROM bank_table WHERE bank=?"
    else:
        sql_stmt = "UPDATE bank_table SET active=0 WHERE bank=?"

    try:
        cur.execute(sql_stmt, (bank,))

        # helper function to traverse the bank table and disable all of its sub banks
        def get_sub_banks(bank):
            select_stmt = "SELECT bank FROM bank_table WHERE parent_bank=?"
            cur.execute(select_stmt, (bank,))
            result = cur.fetchall()

            # we've reached a bank with no sub banks
            if len(result) == 0:
                select_assoc_stmt = """
                    SELECT username, bank
                    FROM association_table WHERE bank=?
                    """
                for assoc_row in cur.execute(select_assoc_stmt, (bank,)):
                    u.delete_user(
                        conn,
                        username=assoc_row["username"],
                        bank=assoc_row["bank"],
                        force=force,
                    )
            # else, disable all of its sub banks and continue traversing
            else:
                for row in result:
                    cur.execute(sql_stmt, (row["bank"],))
                    get_sub_banks(row["bank"])

        get_sub_banks(bank)
        if force:
            # we also need to update the job usage for the rest of the hierarchy as a
            # result of the bank (which may or may not have usage) no longer being in
            # the database hierarchy; start from the root bank and work down
            s_root_bank = "SELECT bank FROM bank_table WHERE parent_bank=''"
            cur.execute(s_root_bank)
            root_bank = cur.fetchone()[0]
            jobs.calc_parent_bank_usage(conn, cur, root_bank)
    # if an exception occurs while recursively deleting
    # the parent banks, then throw the exception and roll
    # back the changes made to the DB
    except sqlite3.OperationalError as exc:
        conn.rollback()
        raise sqlite3.OperationalError(f"an sqlite3.OperationalError occurred: {exc}")

    # commit changes
    conn.commit()
    return 0


@with_cursor
def edit_bank(
    conn,
    cur,
    bank=None,
    shares=None,
    parent_bank=None,
    priority=None,
    ignore_older_than=None,
):
    params = locals()
    editable_fields = [
        "shares",
        "parent_bank",
        "priority",
        "ignore_older_than",
    ]
    for field in editable_fields:
        if params[field] is not None:
            if field == "parent_bank":
                try:
                    validate_parent_bank(cur, params[field])
                except ValueError as bad_parent_bank:
                    raise ValueError(
                        f"parent bank {bad_parent_bank} not found in bank table"
                    )
                except sqlite3.OperationalError as exc:
                    raise sqlite3.OperationalError(exc)
            if field == "shares":
                if int(shares) <= 0:
                    raise ValueError("new shares amount must be > 0")

            update_stmt = "UPDATE bank_table SET " + field

            update_stmt += "=? WHERE bank=?"
            tup = (
                params[field],
                bank,
            )
            cur.execute(update_stmt, tup)

    # commit changes
    conn.commit()

    return 0


@with_cursor
def list_banks(
    conn,
    cur,
    inactive=False,
    cols=None,
    json_fmt=False,
    format_string="",
):
    """
    List all banks in bank_table.

    Args:
        inactive: whether to include inactive banks. By default, only banks that are
            active will be included in the output.
        cols: a list of columns from the table to include in the output. By default, all
            columns are included.
        table: output data in bank_table in table format. By default, the format of any
            returned data is in JSON.
        format_string: a format string defining how each row should be formatted. Column
            names should be used as placeholders.
    """
    # use all column names if none are passed in
    cols = cols or fluxacct.accounting.BANK_TABLE

    sql.validate_columns(cols, fluxacct.accounting.BANK_TABLE)
    # construct SELECT statement
    select_stmt = f"SELECT {', '.join(cols)} FROM bank_table"
    if not inactive:
        select_stmt += " WHERE active=1"
    cur.execute(select_stmt)

    # initialize AccountingFormatter object
    formatter = fmt.AccountingFormatter(cur)
    if format_string != "":
        return formatter.as_format_string(format_string)
    if json_fmt:
        return formatter.as_json()
    return formatter.as_table()


@with_cursor
def bank_info(
    conn,
    cur,
    tree=None,
    tree_no_users=None,
    to_root=None,
    user=None,
    verbose=False,
    parsable=False,
    noheader=False,
    exclude=None,
):
    """
    Display fairshare and priority information for banks and users.

    Args:
        tree: bank name to display all children of, including users
        tree_no_users: bank name to display all children of, excluding users
        to_root: bank name to display all parents for up to root
        user: username to query
        verbose: display detailed usage info
        parsable: output "|" delimited columns for easy parsing
        noheader: do not display headers
        exclude: do not display this bank in output
    """
    # determine which bank/user we're querying
    bank = tree or tree_no_users or to_root

    # get current user if no user or bank specified
    if bank is None and user is None:
        user = pwd.getpwuid(os.getuid()).pw_name

    # if querying a user, get their default bank
    default_bank = None
    if user:
        result = cur.execute(
            "SELECT default_bank FROM association_table WHERE username=? LIMIT 1",
            (user,),
        ).fetchone()
        if result:
            default_bank = result["default_bank"]

    # build the tree structure from the database
    sharetree = _build_sharetree(cur)

    # find the target node(s)
    target_name = user if user else bank
    target_nodes = [
        node for node in sharetree.values() if node["shortname"] == target_name
    ]

    if not target_nodes:
        raise ValueError(f'Could not find "{target_name}"')

    output_lines = []
    if not noheader:
        output_lines.append(fmt.format_bank_info_header(verbose, parsable))

    # display based on mode
    if to_root is not None or (
        user is not None and tree is None and tree_no_users is None
    ):
        # display from target up to root (for banks with -r or users with -u)
        for target in target_nodes:
            node = target
            path = []
            skip_path = False
            while node["depth"] > 0:
                if exclude and node["shortname"] == exclude:
                    skip_path = True
                path.append(
                    fmt.format_bank_info_node(node, default_bank, verbose, parsable)
                )
                node = sharetree[node["parent"]]
            if skip_path:
                continue
            path.append(
                fmt.format_bank_info_node(node, default_bank, verbose, parsable)
            )
            path.reverse()
            output_lines.extend(path)
    elif tree is not None or tree_no_users is not None:
        # display from target down to leaves
        def traverse_down(node, include_users):
            lines = [fmt.format_bank_info_node(node, default_bank, verbose, parsable)]
            for child_name in sorted(node["children"]):
                child = sharetree[f"{node['name']}{child_name}/"]
                if exclude and child["shortname"] == exclude:
                    continue
                if child["isuser"]:
                    if include_users:
                        lines.append(
                            fmt.format_bank_info_node(
                                child, default_bank, verbose, parsable
                            )
                        )
                else:
                    lines.extend(traverse_down(child, include_users))
            return lines

        for target in target_nodes:
            output_lines.extend(traverse_down(target, tree is not None))

    return "\n".join(output_lines)
