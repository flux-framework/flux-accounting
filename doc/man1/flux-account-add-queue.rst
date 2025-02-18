.. flux-help-section: flux account

=========================
flux-account-add-queue(1)
=========================

.. note::

 The queues defined in flux-accounting are for accounting purposes
 (permissions, priority calculation, and limits) only. They are a separate
 construct from queues in flux-core_ and queuing policies in flux-sched_.

SYNOPSIS
========

**flux** **account** **add-queue** QUEUE [OPTIONS]

DESCRIPTION
===========

.. program:: flux account add-queue

:program:`flux account add-queue` will add a queue to the ``queue_table`` in
the flux-accounting database. Different properties and limits can be set for
each queue:

.. option:: --min-nodes-per-job

    The minimum number of nodes required to run jobs in this queue.

.. option:: --max-nodes-per-job

    The maximum number of nodes a job can use in this queue.

.. option:: --max-time-per-job

    The max time a job can be running in this queue.

.. option:: --priority

    An associated priority to be applied to jobs submitted to this queue.

.. option:: --max-running-jobs

    Max number of running jobs an association can have in this queue.

.. _flux-core: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man5/flux-config-queues.html

.. _flux-sched: https://flux-framework.readthedocs.io/projects/flux-sched/en/latest/man5/flux-config-sched-fluxion-qmanager.html
