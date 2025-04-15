.. flux-help-section: flux account

==========================
flux-account-view-queue(1)
==========================

.. note::

 The queues defined in flux-accounting are for accounting purposes
 (permissions, priority calculation, and limits) only. They are a separate
 construct from queues in flux-core_ and queuing policies in flux-sched_.

SYNOPSIS
========

**flux** **account** **view-queue** QUEUE

DESCRIPTION
===========

.. program:: flux account view-queue

:program:`flux account view-queue` returns all of the various attributes for
the queue specified.

.. option:: --parsable

    Prints all information about each queue on one line.

.. option:: -o/--format

    Specify output format using Python's string format syntax.

.. _flux-core: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man5/flux-config-queues.html

.. _flux-sched: https://flux-framework.readthedocs.io/projects/flux-sched/en/latest/man5/flux-config-sched-fluxion-qmanager.html
