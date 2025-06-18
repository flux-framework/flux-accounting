.. flux-help-section: flux account

============================
flux-account-list-factors(1)
============================

SYNOPSIS
========

**flux** **account** **list-factors** FACTOR

DESCRIPTION
===========

.. program:: flux account list-factors

:program:`flux account list-factors` will list all of the priority factors in
the ``priority_factor_weight_table``. By default, it will include every column
in the ``priority_factor_weight_table``, but the output can be customized by
specifying which columns to include.

.. option:: --fields

    A list of columns from the table to include in the output. By default, all
    columns are included.

.. option:: --json

    Output data in JSON format. By default, the format of any returned data is
    in a table format.

.. option:: -o/--format

    Specify output format using Python's string format syntax.
