.. flux-help-section: flux account

==============================
flux-account-edit-all-users(1)
==============================


SYNOPSIS
========

**flux** **account** **edit-all-users** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account edit-all-users

:program:`flux account edit-all-users` allows for the modification of certain
fields for *every* association in ``association_table``. The list of modifiable
fields are as follows:

.. option:: --bank

    The bank that every association belongs to.

.. option:: --default-bank

    The default bank that every association belongs to.

.. option:: --shares

    The amount of available resources their organization considers every
    association should be entitled to use relative to other competing users.

.. option:: --fairshare

    The ratio between the amount of resources every association is allocated
    versus the amount actually consumed.

.. option:: --max-running-jobs

    The max number of running jobs each association can have at any given time.

.. option:: --max-active-jobs

    The max number of both pending and running jobs each association can have at
    any given time.

.. option:: --max-nodes

    The max number of nodes each association can have across all of their running
    jobs.

.. option:: --max-cores

    The max number of cores each association can have across all of their running
    jobs.

.. option:: --queues

    A comma-separated list of all of the queues each association can run jobs
    under.

.. option:: --projects

    A comma-separated list of all of the projects each association can run jobs
    under.

.. option:: --default-project

    The default project each association will submit jobs under when they do not
    specify a project.

.. option:: --max-sched-jobs

    The max number of jobs in SCHED state an association can have at any given
    time.

Most of the attributes able to be modified can be reset to their default value
by passing ``-1`` as the value for the field. Multiple fields can be edited at
the same time by passing them on the command line.
