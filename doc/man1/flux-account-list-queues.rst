.. flux-help-section: flux account

===========================
flux-account-list-queues(1)
===========================

.. note::

 The queues defined in flux-accounting are for accounting purposes
 (permissions, priority calculation, and limits) only. They are a separate
 construct from queues in flux-core_ and queuing policies in flux-sched_.

SYNOPSIS
========

**flux** **account** **list-queues**

DESCRIPTION
===========

.. program:: flux account list-queues

:program:`flux account list-queues` will list all of the queues in the
``queue_table``. By default, it will include every column in the
``queue_table``, but the output can be customized by specifying which columns
to include.

.. option:: --fields

    A list of columns from the table to include in the output. By default, all
    columns are included.

.. option:: --json

    Output data in JSON format. By default, the format of any returned data is
    in a table format.

.. option:: -o/--format

    Specify output format using Python's string format syntax.

.. _flux-core: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man5/flux-config-queues.html

.. _flux-sched: https://flux-framework.readthedocs.io/projects/flux-sched/en/latest/man5/flux-config-sched-fluxion-qmanager.html
