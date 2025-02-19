.. flux-help-section: flux account

==========================
flux-account-list-banks(1)
==========================


SYNOPSIS
========

**flux** **account** **list-banks**

DESCRIPTION
===========

.. program:: flux account list-banks

:program:`flux account list-banks` will list all of the banks in the
``bank_table``. By default, it will include every column in the ``bank_table``,
but the output can be customized by specifying which columns to include.

.. option:: --inactive

    Include inactive banks in the output.

.. option:: --fields

    A list of columns from the table to include in the output. By default, all
    columns are included.

.. option:: --table

    Output data in table format. By default, the format of any returned data is
    in JSON.
