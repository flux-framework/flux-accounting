.. flux-help-section: flux account

=========================
flux-account-view-bank(1)
=========================


SYNOPSIS
========

**flux** **account** **view-bank** BANK [OPTIONS]

DESCRIPTION
===========

.. program:: flux account view-bank

:program:`flux account view-bank` returns all of the various attributes for
the bank specified. Options can be passed in to view all users that belong to
this bank or view the bank in relation to other banks in the flux-accounting
database hierarchy.

.. option:: --tree

    View the flux-accounting database hierarchy in a tree format where BANK is
    the root of the tree.

.. option:: --parsable

    Similar to ``--tree``, view the flux-accounting database hierarchy in a
    tree format where BANK is the root of the tree, delimited by a pipe (``|``)
    character.

.. option:: --users

    List every user that belongs to BANK, along with their basic accounting
    information.

.. option:: --fields

    Customize which fields are returned in the output of ``view-bank``.

.. option:: -o/--format

    Specify output format using Python's string format syntax.

.. option:: -c/--concise

    Only list associations under this bank that have contributed to the bank's
    current job usage value.
