.. flux-help-section: flux account

========================
flux-account-add-user(1)
========================


SYNOPSIS
========

**flux** **account** **add-user** --username=USERNAME --bank=BANK [OPTIONS]

DESCRIPTION
===========

.. program:: flux account add-user

:program:`flux account add-user` will add an *association* to the
``association_table`` in the flux-accounting database. An *association* is
defined as a 2-tuple combination of a username and bank name. It requires two
arguments: the *username* of the association and the *bank* they are being
added under. Additional configurable fields, such as the number of allocated
shares, a default bank, various job limits, permissible queues, etc. may also
be defined upon user creation.

.. option:: -u/--username

    The username of the association.

.. option:: -i/--userid

    The userid of the association.

.. option:: -B/--bank

    The bank of the association. Users submitting jobs under this bank will
    contribute both to their own usage as well as the bank's total usage.

.. option:: --shares

    The amount of available resources their organization considers they should
    be entitled to use relative to other competing users.

.. option:: --fairshare

    The ratio between the amount of resources an association is allocated
    versus the amount actually consumed.

.. option:: --max-running-jobs

    The max number of running jobs the association can have at any given time.

.. option:: --max-active-jobs

    The max number of both pending and running jobs the association can have at
    any given time.

.. option:: -N/--max-nodes

    The max number of nodes an association can have across all of their running
    jobs.

.. option:: -c/--max-cores

    The max number of cores an association can have across all of their running
    jobs.

.. option:: -q/--queues

    A comma-separated list of all of the queues an association can run jobs
    under.

.. option:: -P/--projects

    A comma-separated list of all of the projects an association can run jobs
    under. If this option is passed, the **first** project listed will become
    the association's default project. The association's default can be changed
    with :man1:`flux-account-edit-user`.

.. option:: --default-project

    The default project an association will run jobs under.

EXAMPLES
--------

An association can be added to the flux-accounting database simply by
specifying the username and the bank name:

.. code-block:: console

 $ flux account add-user --username=moose --bank=bankA

Or fully configured by specifying any additional number of options:

.. code-block:: console

 $ flux account add-user --username=moose --bank=bankA --queues=queue1,queue2 --shares=1
