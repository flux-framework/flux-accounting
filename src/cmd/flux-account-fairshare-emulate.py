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
import argparse
import json
import sys

from fluxacct.accounting import fairshare_emulator


def main():
    parser = argparse.ArgumentParser(description="""
        Fair-share emulator: Calculate fair-share values from JSON input
        without requiring a database. Useful for testing fair-share scenarios
        and previewing changes before applying them to production.
        """)

    parser.add_argument(
        "-i",
        "--input",
        dest="input_file",
        required=True,
        help="path to input JSON file containing bank hierarchy, shares, and usage",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="output results as JSON",
    )
    parser.add_argument(
        "-o",
        "--format",
        dest="format_string",
        default="",
        help="output results using Python format string (e.g., '{username} {fairshare}')",
    )
    parser.add_argument(
        "--parsable",
        "-P",
        action="store_true",
        help="output results in parsable pipe-delimited format",
    )

    args = parser.parse_args()

    try:
        with open(args.input_file, "r") as input_file:
            json_data = json.load(input_file)
    except FileNotFoundError:
        print(
            f"fairshare-emulate: FileNotFoundError: input file not found: {args.input_file}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(
            f"fairshare-emulate: JSONDecodeError: invalid JSON in input file: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        root = fairshare_emulator.parse_json_input(json_data)
    except ValueError as exc:
        print(f"fairshare-emulate: ValueError: {exc}", file=sys.stderr)
        sys.exit(1)

    calculator = fairshare_emulator.FairShareCalculator(root)
    users = calculator.calculate()

    if args.parsable:
        format_string = "{username}|{bank}|{shares}|{usage}|{fairshare}"
    else:
        format_string = args.format_string

    try:
        output = fairshare_emulator.format_results(
            users, json_fmt=args.json, format_string=format_string
        )
        print(output)
    except ValueError as exc:
        print(f"fairshare-emulate: ValueError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
