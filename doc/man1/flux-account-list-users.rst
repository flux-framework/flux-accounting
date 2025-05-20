.. flux-help-section: flux account

==========================
flux-account-list-users(1)
==========================


SYNOPSIS
========

**flux** **account** **list-users** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account list-users

:program:`flux account list-users` will list all of the associations in the
``association_table``. By default, it will include every column in the
``association_table``, but the output can be customized by specifying which
columns to include. The table can also be filtered to return associations that
meet certain criteria, such as those who belong to a certain bank, queue, or
project, or those who have certain configured limits.

.. option:: -f/--fields

    A list of columns from the table to include in the output. By default, all
    columns are included.

.. option:: -j/--json

    Output in JSON format.

.. option:: -o/--format

    Specify output format using Python's string format syntax.

.. option:: --active

    An association's active status (1 = active; 0 = inactive)

.. option:: -B/--bank

    The bank(s) that associations belong to.

.. option:: --shares

    The amount of available resources their organization considers they should
    be entitled to use relative to other competing users.

.. option:: --max-running-jobs

    The max number of running jobs the association can have at any given time.

.. option:: --max-active-jobs

    The max number of both pending and running jobs the association can have at
    any given time.

.. option:: -N/--max-nodes

    The max number of nodes an association can have across all of their running
    jobs.
    
.. option:: -c/--max-cores

    The max number of nodes an association can have across all of their running
    jobs.

.. option:: -q/--queues

    A comma-separated list of all of the queues an association can run jobs
    under.

.. option:: -P/--projects

    A comma-separated list of all of the projects an association can run jobs
    under.

.. option:: --default-project

    The default project an association belongs to.
