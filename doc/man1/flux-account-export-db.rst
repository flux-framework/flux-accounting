.. flux-help-section: flux account

=========================
flux-account-export-db(1)
=========================


SYNOPSIS
========

**flux** **account** **export-db** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account export-db

:program:`flux account export-db` will extract flux-accounting database
information into separate ``.csv`` files, or as hierarchical JSON for the
fairshare emulator when the ``--fairshare-emulate`` option is specified.

OPTIONS
=======

.. option:: -F, --fairshare-emulate

    Export database as a hierarchical JSON structure suitable for use
    with :program:`flux account fairshare-emulate`. This option outputs
    a single JSON file to stdout instead of creating CSV files.

.. option:: -u, --users

    Path to a ``.csv`` file containing user information.

.. option:: -b, --banks

    Path to a ``.csv`` file containing bank information.

The order of columns extracted from the ``association_table``:

**Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues**

The order of columns extracted from the ``bank_table``:

**Bank,ParentBank,Shares**

If no custom path is specified, this will create a file in the current working
directory called ``users.csv`` and ``banks.csv``.
