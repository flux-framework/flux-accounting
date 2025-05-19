.. flux-help-section: flux account

=============================
flux-account-list-projects(1)
=============================

SYNOPSIS
========

**flux** **account** **list-projects**

DESCRIPTION
===========

.. program:: flux account list-projects

:program:`flux account list-projects` will list all of the projects in the
``project_table``. By default, it will include every column in the
``project_table``, but the output can be customized by specifying which columns
to include.

.. option:: --fields

    A list of columns from the table to include in the output. By default, all
    columns are included.

.. option:: --json

    Output data in JSON format. By default, the format of any returned data is
    in a table format.

.. option:: -o/--format

    Specify output format using Python's string format syntax.
