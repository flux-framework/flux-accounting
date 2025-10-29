.. flux-help-section: flux account

====================
flux-account-jobs(1)
====================


SYNOPSIS
========

**flux** **account** **jobs** USERNAME [OPTIONS]

DESCRIPTION
===========

.. program:: flux account jobs

:program:`flux account jobs` will output a breakdown of an association's job's
priority calculations. Jobs can be filtered by bank or by queue.

.. option:: --bank=BANK

    Filter to only output jobs that have run under a specific bank.

.. option:: --queue=QUEUE

    Filter to only output jobs that have run under a specific queue.

.. option:: -o/--format=FORMAT

    Specify output format using Python's string format syntax.

.. option:: --filter=STATES|RESULTS

    Filter to only output jobs that are in certain states. Available options
    are: "depend", "priority", "sched", "run", "cleanup", "inactive",
    "pending", "running", "active", "completed", "failed", "canceled", and
    "timeout"

.. option:: -c/--count=N

    Limit output to only show N jobs (default will show all jobs for a given
    association).

.. option:: --since=WHEN

    Only show jobs that have become inactive since WHEN. A seconds-since-epoch
    timestamp or a human-readable timestamp (e.g. ``"2025-05-20 08:00:00"``)
    can be passed.

.. option:: -j/--jobids=[JOBIDS]

    Return the priority calculation for one or more job IDs.

.. option:: -v/--verbose

    Output a detailed breakdown of how the priority was calculated for each
    job, showing how each factor relates to one another to come up with the
    final priority displayed in the ``PRIORITY`` column.
