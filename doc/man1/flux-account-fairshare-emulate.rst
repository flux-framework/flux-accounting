.. flux-help-section: flux account

=================================
flux-account-fairshare-emulate(1)
=================================


SYNOPSIS
========

**flux** **account-fairshare-emulate** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account-fairshare-emulate

:program:`flux account-fairshare-emulate` calculates fair-share values
from a JSON input file without requiring a database. This command is
useful for testing fair-share scenarios, previewing the effects of
configuration changes before applying them to production, and for
educational or documentation purposes.

The fair-share algorithm is a weighted tree traversal that considers
bank hierarchies, user shares, and historical job usage to calculate
priority values. This emulator implements the same algorithm as
:program:`flux-account-update-fshare`, allowing you to experiment with
different configurations offline.

OPTIONS
=======

.. option:: -i, --input FILE

   Path to input JSON file containing the bank hierarchy, shares, and
   usage values. This option is required.

.. option:: --json, -j

   Output results in JSON format. Each user is represented as a JSON
   object with username, bank, shares, usage, and fair-share fields.

.. option:: -o, --format FORMAT_STRING

   Output results using a Python format string. Available fields are:
   {username}, {bank}, {shares}, {usage}, and {fairshare}.
   Example: "{username:<10} {fairshare:.4f}"

.. option:: --parsable, -P

   Output results in pipe-delimited format suitable for parsing:
   username|bank|shares|usage|fairshare

JSON INPUT FORMAT
=================

The input JSON file must contain a "root" key with a hierarchical
structure of banks and users. Each node in the hierarchy must have:

- **shares**: allocation shares (integer)
- **usage**: historical job usage (float)
- **bank**: bank name (for bank nodes)
- **username**: user name (for leaf user nodes)
- **children**: array of child nodes (optional, for bank nodes)

Nodes with a "username" field are treated as leaf user associations.
Nodes with a "bank" field and "children" array are treated as banks.

EXAMPLE JSON
============

.. code-block:: json

    {
      "root": {
        "bank": "root",
        "shares": 1000,
        "usage": 132,
        "children": [
          {
            "bank": "bank1",
            "shares": 1000,
            "usage": 121,
            "children": [
              {"username": "user1", "shares": 10000, "usage": 100},
              {"username": "user2", "shares": 1000, "usage": 11},
              {"username": "user3", "shares": 100000, "usage": 10}
            ]
          },
          {
            "bank": "bank2",
            "shares": 100,
            "usage": 11,
            "children": [
              {"username": "user4", "shares": 100000, "usage": 8},
              {"username": "user5", "shares": 10000, "usage": 3}
            ]
          }
        ]
      }
    }

SEE ALSO
========

flux-account-update-fshare(1), flux-account-update-usage(1)
