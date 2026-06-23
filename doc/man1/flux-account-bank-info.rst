.. flux-help-section: flux account

=========================
flux-account-bank-info(1)
=========================


SYNOPSIS
========

**flux** **account** **bank-info** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account bank-info

:program:`flux account bank-info` displays fair-share and shares information
for banks and users in the database. By default, if no options are specified,
it shows information for the current user.

.. option:: -t/--tree <bank>

    Display all children of <bank>, including users.

.. option:: -T/--tree-no-users <bank>

    Display all children of <bank>, excluding users.

.. option:: -r/--to-root <bank>

    Display all parents for <bank> up to the root.

.. option:: -u/--user <user>

    Display all banks for <user>.

.. option:: -v/--verbose

    Display detailed usage information.

.. option:: -P/--parsable

    Output pipe (``|``) delimited columns for easy parsing.

.. option:: -n/--noheader

    Do not display column headers.

.. option:: -x/--exclude <bank>

    Do not display <bank> in output (defaults to 'expired').
