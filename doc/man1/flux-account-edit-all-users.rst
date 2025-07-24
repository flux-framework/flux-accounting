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

    The bank that the user belongs to.

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

Most of the attributes able to be modified can be reset to their default value
by passing ``-1`` as the value for the field. Multiple fields can be edited at
the same time by passing them on the command line.
