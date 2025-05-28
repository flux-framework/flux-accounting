.. flux-help-section: flux account

========================
flux-account-add-bank(1)
========================


SYNOPSIS
========

**flux** **account** **add-bank** BANK SHARES [--parent-bank=PARENT-BANK]

DESCRIPTION
===========

.. program:: flux account add-bank

:program:`flux account add-bank` will add a new bank to the ``bank_table`` in
the flux-accounting database. If the bank being added is not the root bank, its
parent must be specified when added. Shares allocated to the bank can also be
configured when adding the bank.

.. option:: --parent-bank

    The name of the parent bank.

.. option:: --priority

    An associated priority to be applied to jobs submitted under this bank.

EXAMPLES
--------

A parent bank does not need to be specified when adding the root bank:

.. code-block:: console

    $ flux account add-bank root 1

All others, however, require a parent bank:

.. code-block:: console

    $ flux account add-bank bankA 1 --parent-bank=root
