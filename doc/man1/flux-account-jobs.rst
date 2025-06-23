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

.. option:: --bank

    Filter to only output jobs that have run under a specific bank.

.. option:: --queue

    Filter to only output jobs that have run under a specific queue.

.. option:: -o/--format

    Specify output format using Python's string format syntax.
