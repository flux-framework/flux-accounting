.. flux-help-section: flux account

=========================
flux-account-edit-user(1)
=========================


SYNOPSIS
========

**flux** **account** **edit-user** --username=USERNAME [--bank=BANK] [OPTIONS]

DESCRIPTION
===========

.. program:: flux account edit-user

:program:`flux account edit-user` allows for the modifications of certain
fields for a given association. The list of modifiable fields are as follows:

.. option:: --userid

    The userid of the association.

.. option:: --bank

    An optional bank name that can be specified. If left out, the update will
    be applied across all of the rows in ``association_table`` where
    ``username`` is found.

.. option:: --shares

    The amount of available resources their organization considers they should
    be entitled to use relative to other competing users.

.. option:: --max-running-jobs

    The max number of running jobs the association can have at any given time.

.. option:: --max-active-jobs

    The max number of both pending and running jobs the association can have at
    any given time.

.. option:: --max-nodes

    The man number of nodes an association can have across all of their running
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

EXAMPLES
--------

Multiple attributes for an association can be edited at the same time:

.. code-block:: console

    $ flux account edit-user moose --max-active-jobs=100 --queues="special,expedite"

An association's attributes can be reset to their default value by passing
``-1``:

.. code-block:: console

    $ flux account edit-user moose --max-active-jobs=-1
