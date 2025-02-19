.. flux-help-section: flux account

===========================
flux-account-delete-bank(1)
===========================


SYNOPSIS
========

**flux** **account** **delete-bank** BANK

DESCRIPTION
===========

.. program:: flux account delete-bank

:program:`flux account delete-bank` will set a bank's ``active`` field to ``0``
in the ``bank_table``. Banks can be reactivated by simply re-adding them to the
``bank_table`` with ``flux account add-bank``.

To actually remove a bank from the ``bank_table``, pass the ``--force`` option.

.. warning::
    Permanently deleting rows from the ``bank_table`` can affect the fair-share
    calculation for other rows in the ``bank_table`` and ``association_table``.
    Proceed with caution when deleting rows with ``--force``.

EXAMPLES
--------

A bank can be deactivated by calling ``delete-bank``:

.. code-block:: console

    $ flux account delete-bank bankA
