.. flux-help-section: flux account

======================
flux-account-pop-db(1)
======================


SYNOPSIS
========

**flux** **account** **pop-db** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account pop-db

:program:`flux account pop-db` will populate an already-existing
flux-accounting database with a ``.csv`` file.

.. option:: -u, --users

    Path to a ``.csv`` file containing user information.

.. option:: -b, --banks

    Path to a ``.csv`` file containing bank information.

The order of elements required for populating the ``association_table`` are as
follows:

**Username,UserID,Bank,Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes,Queues**

**Shares,MaxRunningJobs,MaxActiveJobs,MaxNodes** can be left blank (``''``) in
the ``.csv`` file for a given row.

The order of elements required for populating the ``bank_table`` are as
follows:

**Bank,ParentBank,Shares**

**Shares** can be left blank (``''``) in the ``.csv`` file for a given row.
