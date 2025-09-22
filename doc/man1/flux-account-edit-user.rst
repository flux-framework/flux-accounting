.. flux-help-section: flux account

=========================
flux-account-edit-user(1)
=========================


SYNOPSIS
========

**flux** **account** **edit-user** USERNAME [--bank=BANK] [OPTIONS]

DESCRIPTION
===========

.. program:: flux account edit-user

:program:`flux account edit-user` allows for the modifications of certain
fields for a given association. Passing the ``--bank`` option will specify a
specific row for the update to be applied. If left out, the update will be
applied across all of the rows in ``association_table`` where ``username`` is
found.

The list of modifiable fields for an association are as follows:

.. option:: --userid

    The userid of the association.

.. option:: --default-bank

    The default bank that the user belongs to.

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

.. option:: --max-nodes

    The max number of nodes an association can have across all of their running
    jobs.

.. option:: --max-cores

    The max number of cores an association can have across all of their running
    jobs.

.. option:: --queues

    A comma-separated list of all of the queues an association can run jobs
    under.

.. option:: --projects

    A comma-separated list of all of the projects an association can run jobs
    under.

.. option:: --default-project

    The default project the association will submit jobs under when they do not
    specify a project.

All of the attributes able to be modified can be reset to their default value
by passing ``-1`` as the value for the field. Multiple fields can be edited at
the same time by passing them on the command line.

The ``max_nodes`` and ``max_cores`` fields can also be reset to their maximum
value (``2147483647``) by passing ``"unlimited"``.

EXAMPLES
--------

Multiple attributes for an association can be edited at the same time:

.. code-block:: console

    $ flux account edit-user moose --max-active-jobs=100 --queues="special,expedite"

An association's attributes can be reset to their default value by passing
``-1``:

.. code-block:: console

    $ flux account edit-user moose --max-active-jobs=-1
