.. flux-help-section: flux account

============================
flux-account-delete-queue(1)
============================

.. note::

 The queues defined in flux-accounting are for accounting purposes
 (permissions, priority calculation, and limits) only. They are a separate
 construct from queues in flux-core_ and queuing policies in flux-sched_.

SYNOPSIS
========

**flux** **account** **delete-queue** QUEUE

DESCRIPTION
===========

.. program:: flux account delete-queue

:program:`flux account delete-queue` will remove a queue from the
``queue_table`` in the flux-accounting database. Note that removing a queue
from this table will not automatically remove any references to this queue
elsewhere in the flux-accounting DB, particularly the ``association_table``.
If associations still reference this queue, a ``WARNING`` message will be
returned reminding the user to also remove this queue from all associations'
rows.

.. _flux-core: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man5/flux-config-queues.html

.. _flux-sched: https://flux-framework.readthedocs.io/projects/flux-sched/en/latest/man5/flux-config-sched-fluxion-qmanager.html
