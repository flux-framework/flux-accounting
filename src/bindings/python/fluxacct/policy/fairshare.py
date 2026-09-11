#!/usr/bin/env python3

###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sys
import json


class FairShareNode:
    """Represents a node in the fair-share hierarchy."""

    EPSILON = 1e-9
    MAX_UINT64 = (1 << 64) - 1

    def __init__(self, name, shares, usage, bank=None, is_user=False):
        self.name = name
        self.bank = bank
        self.shares = shares
        self.usage = usage
        self.is_user = is_user
        self.children = []
        self.weight = 0.0
        self.fairshare = 0.5
        self.tie_with_next = False

    def add_child(self, child):
        self.children.append(child)

    def calculate_children_weights(self):
        """Calculate weights for all children based on shares/usage ratios."""
        if not self.children:
            return

        # sum shares and usage across siblings
        sibling_shares_sum = sum(c.shares for c in self.children)
        sibling_usage_sum = sum(c.usage for c in self.children)

        # calculate weight for each child
        for child in self.children:
            child.calculate_weight(sibling_shares_sum, sibling_usage_sum)

    def calculate_weight(self, sibling_shares_sum, sibling_usage_sum):
        """Calculate weight for this node based on shares/usage ratio."""
        if self.shares == 0:
            self.weight = 0.0
        elif abs(self.usage) < self.EPSILON:
            # zero usage → highest priority
            self.weight = float(self.MAX_UINT64) + 1.0
        else:
            s_weight = self.shares / sibling_shares_sum
            u_weight = self.usage / sibling_usage_sum
            # higher shares + lower usage = higher weight
            self.weight = s_weight / u_weight

    def sort_children_by_weight(self):
        """Sort children by weight descending (highest weight first)."""
        self.children.sort(key=lambda c: c.weight, reverse=True)

    def mark_ties(self):
        """Mark children that have equal weights with their next sibling."""
        for i in range(len(self.children) - 1):
            curr = self.children[i]
            next_child = self.children[i + 1]
            # only tie if both are users or both are banks
            if curr.is_user == next_child.is_user:
                if self.is_equal(curr.weight, next_child.weight):
                    curr.tie_with_next = True

    @staticmethod
    def is_equal(val_a, val_b):
        """Floating-point equality check."""
        threshold = sys.float_info.epsilon * max(abs(val_a), max(abs(val_b), 1.0))
        return abs(val_a - val_b) < threshold


class FairShareCalculator:
    """Implements the weighted tree fair-share algorithm."""

    def __init__(self, root_node):
        self.root = root_node
        self.users = []
        self.current_rank = 0
        self.stride_size = 0
        self.total_users = 0

    def calculate(self):
        """Calculate fair-share values for all users in the tree."""
        # count total users
        total_users = self._count_users(self.root)
        if total_users == 0:
            return []

        # calculate weights throughout the tree
        self._calculate_all_weights(self.root)

        # sort children by weight and mark ties
        self._prepare_tree(self.root)

        # traverse and assign fair-share values
        # rank starts at total_users for highest priority, counts down
        self.current_rank = total_users
        self.stride_size = 0
        self.users = []
        self.total_users = total_users
        self._traverse(self.root)

        return self.users

    def _count_users(self, node):
        """Count leaf users in tree."""
        if node.is_user:
            return 1
        return sum(self._count_users(c) for c in node.children)

    def _calculate_all_weights(self, node):
        """Recursively calculate weights for all nodes."""
        node.calculate_children_weights()
        for child in node.children:
            if not child.is_user:
                self._calculate_all_weights(child)

    def _prepare_tree(self, node):
        """
        Sort children and mark ties throughout the tree.
        Recursively prepares all bank nodes in the hierarchy.
        """
        if not node.children:
            return

        # recursively prepare each child bank
        for child in node.children:
            if not child.is_user:
                self._prepare_tree(child)

        # sort and mark ties at this level
        node.sort_children_by_weight()
        node.mark_ties()

    @staticmethod
    def _build_tie_aware_children(node):
        """Build a tie-aware children list, merging grandchildren from tied banks."""
        tie_aware = []
        in_stride = False
        virtual_children = []

        for i, child in enumerate(node.children):
            # User children are added directly
            if child.is_user:
                tie_aware.append(child)
                continue

            # Bank children: check if tied with next
            is_tied = (
                i < len(node.children) - 1
                and FairShareNode.is_equal(child.weight, node.children[i + 1].weight)
                and not child.is_user
                and not node.children[i + 1].is_user
            )

            if is_tied:
                if not in_stride:
                    # Start of a new tie group
                    in_stride = True
                    virtual_children = []
                # Add this bank's children to the virtual node
                virtual_children.extend(child.children)
            else:
                if in_stride:
                    # End of tie group - add last bank's children
                    virtual_children.extend(child.children)
                    # Sort merged children and add as virtual node
                    virtual_children.sort(key=lambda c: c.weight, reverse=True)
                    # Mark ties within the merged group
                    for j in range(len(virtual_children) - 1):
                        if FairShareNode.is_equal(
                            virtual_children[j].weight, virtual_children[j + 1].weight
                        ):
                            virtual_children[j].tie_with_next = True
                    tie_aware.extend(virtual_children)
                    in_stride = False
                    virtual_children = []
                else:
                    # Not tied, add bank as-is
                    tie_aware.append(child)

        return tie_aware

    def _traverse(self, node):
        """
        Depth-first traversal to assign fair-share values.
        From weighted_walk.cpp::handle_leaf() and handle_internal()

        Rank starts at total_users for the highest priority user.
        Tied users all get the same rank (and thus same fairshare).
        After processing all tied users, rank decrements by 1 + stride_size.

        fairshare = current_rank / total_users
        """
        if node.is_user:
            # Calculate fairshare using current rank
            node.fairshare = self.current_rank / self.total_users

            # Handle ties: tied nodes all use the SAME rank
            if node.tie_with_next:
                # This node is tied with the next one
                # Don't decrement rank yet, just increment stride
                self.stride_size += 1
                node.tie_with_next = False
            else:
                # This node is NOT tied with next (or is the last of a tie group)
                # Decrement rank by 1 + number of nodes we were tied with
                self.current_rank = self.current_rank - 1 - self.stride_size
                self.stride_size = 0

            self.users.append(node)
        else:
            # For internal nodes, build tie-aware children list
            # This merges grandchildren from tied banks
            tie_aware_children = self._build_tie_aware_children(node)

            # Traverse tie-aware children
            for child in tie_aware_children:
                self._traverse(child)


def parse_json_input(json_data):
    """
    Parse JSON input and build fair-share tree.

    Expected format:
    {
      "root": {
        "bank": "root",
        "shares": 1000,
        "usage": 133,
        "children": [
          {
            "bank": "account1",
            "shares": 1000,
            "usage": 121,
            "children": [
              {"username": "user1", "shares": 10000, "usage": 100},
              ...
            ]
          },
          ...
        ]
      }
    }
    """
    if "root" not in json_data:
        raise ValueError("JSON must contain 'root' key")

    root_data = json_data["root"]
    return _build_tree(root_data, parent_bank=None)


def _build_tree(node_data, parent_bank):
    """Recursively build tree from JSON data."""
    # determine if this is a user or bank node
    is_user = "username" in node_data
    name = node_data.get("username") if is_user else node_data.get("bank")

    if not name:
        raise ValueError("Node must have 'username' or 'bank' key")

    shares = node_data.get("shares", 1)
    usage = node_data.get("usage", 0.0)

    # for users, bank is the parent; for banks, bank is self
    bank = parent_bank if is_user else name

    node = FairShareNode(name, shares, usage, bank=bank, is_user=is_user)

    # recursively add children
    if "children" in node_data:
        for child_data in node_data["children"]:
            child = _build_tree(child_data, parent_bank=bank)
            node.add_child(child)

    return node


def format_results(users, json_fmt=False, format_string=""):
    """Format fair-share results for output."""
    if not users:
        raise ValueError("no users found in input")

    if json_fmt:
        results = []
        for user in users:
            results.append(
                {
                    "username": user.name,
                    "bank": user.bank,
                    "shares": user.shares,
                    "usage": user.usage,
                    "fairshare": round(user.fairshare, 6),
                }
            )
        return json.dumps(results, indent=2)

    if format_string:
        lines = []
        for user in users:
            try:
                lines.append(
                    format_string.format(
                        username=user.name,
                        bank=user.bank,
                        shares=user.shares,
                        usage=user.usage,
                        fairshare=round(user.fairshare, 6),
                    )
                )
            except KeyError as err:
                raise ValueError(f"Invalid format string key: {err}") from err
        return "\n".join(lines)

    # default: table format
    rows = []
    for user in users:
        rows.append(
            (
                user.name,
                user.bank,
                user.shares,
                round(user.usage, 2),
                round(user.fairshare, 6),
            )
        )

    headers = ["Username", "Bank", "Shares", "Usage", "FairShare"]
    col_widths = [
        max(len(str(header)), max(len(str(row[i])) for row in rows))
        for i, header in enumerate(headers)
    ]

    def format_row(row):
        return " | ".join(
            f"{str(val).ljust(col_widths[i])}" for i, val in enumerate(row)
        )

    header = format_row(headers)
    separator = "-+-".join(["-" * width for width in col_widths])
    data_rows = "\n".join([format_row(row) for row in rows])

    return f"{header}\n{separator}\n{data_rows}"
