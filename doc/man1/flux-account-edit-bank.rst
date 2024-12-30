.. flux-help-section: flux account

=========================
flux-account-edit-bank(1)
=========================


SYNOPSIS
========

**flux** **account** **edit-bank** BANK [OPTIONS]

DESCRIPTION
===========

.. program:: flux account edit-bank

:program:`flux account edit-bank` allows for the modifications of certain
fields for a given bank. The list of modifiable fields are as follows:

.. option:: --parent-bank

    The name of the parent bank.

.. option:: --shares

    The amount of available resources their organization considers the bank 
    should be entitled to use relative to other competing banks.

EXAMPLES
--------

.. code-block:: console

    $ flux account edit-bank bankA --shares=100
