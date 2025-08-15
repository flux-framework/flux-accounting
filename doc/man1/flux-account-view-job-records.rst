.. flux-help-section: flux account

================================
flux-account-view-job-records(1)
================================


SYNOPSIS
========

**flux** **account** **view-job-records** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account view-job-records

:program:`flux account view-job-records` will display completed job records
stored in the flux-accounting database's ``jobs`` table. The table can be
filtered to show job records by multiple parameters to only return a subset of
job records.

.. option:: -u/--user

    Only return jobs submitted by a certain username.

.. option:: -j/--jobid

    Return a job record for a specific job ID. The job ID can be of any accepted
    `Flux locally unique ID`_.

.. option:: -a/--after-start-time

    Return jobs that have started after a certain time. The timestamp can be in
    seconds-since-epoch or a human readable timestamp (e.g. ``'01/01/2025'``,
    ``'2025-01-01 08:00:00'``, ``'Jan 1, 2025 8am'``).

.. option:: -b/--before-end-time

    Return jobs that have completed before a certain time. The timestamp can be
    in seconds-since-epoch or a human readable timestamp (e.g.
    ``'01/01/2025'``, ``'2025-01-01 08:00:00'``, ``'Jan 1, 2025 8am'``).

.. option:: --project

    Return jobs that were run under a certain project.

.. option:: -B/--bank

    Return jobs that were run under a certain bank.

.. option:: -d/--requested-duration

    Return jobs that fit a certain requested duration's criteria by passing an
    expression. Multiple filters can be passed to refine the
    ``requested_duration`` column by. Expressions can be started with any of
    the following operators: ``<``, ``<=``, ``=``, ``>=``, or ``>``.

.. option:: -e/--actual-duration

    Return jobs that fit a certain actual duration's criteria by passing an
    expression Multiple filters can be passed to refine the ``actual_duration``
    column by. Expressions can be started with any of the following operators:
    ``<``, ``<=``, ``=``, ``>=``, or ``>``.

.. option:: -o/--format

    Specify output format using Python's string format syntax. The available
    fields are: (jobid,username,userid,t_submit,t_run,t_inactive,nnodes
    project,bank)

EXAMPLES
--------

Passing a job ID will return just the job record for that specific ID:

.. code-block:: console

  $ flux account view-job-records --jobid fPeYLgX
  jobid           | username | userid   | t_submit        | t_run           | t_inactive      | nnodes   | project  | bank
  14965276672     | 5001     | 5001     | 1750178607.79   | 1750178607.82   | 1750178607.88   | 1        | *        | bankA

Or filtered to show jobs from a certain time range:

.. code-block:: console

  $ flux account view-job-records --after-start-time="2025-05-01 08:00:00"
  jobid           | username | userid   | t_submit        | t_run           | t_inactive      | nnodes   | project  | bank
  17297309696     | 5001     | 5001     | 1750178934.61   | 1750178934.63   | 1750178934.74   | 1        | *        | bankA
  15015608320     | 5001     | 5001     | 1750178934.47   | 1750178934.49   | 1750178934.69   | 1        | *        | bankA

And customized using Python's string format syntax:

.. code-block:: console

  $ flux account view-job-records -o "{userid:<8} || {t_inactive:<12.3f}"
  userid   || t_inactive  
  5001     || 1750178788.333
  5001     || 1750178788.419
  5001     || 1750178788.238
  5001     || 1750178788.147
  5001     || 1750178789.810

To filter the ``jobs`` table by duration values, you can pass an expression:

.. code-block:: console

  $ flux account view-job-records -d "< 60"

The above will filter job records with a requested duration *less than* 60
seconds long.

Multiple expressions can be passed to further filter the ``requested_duration``
column:

.. code-block:: console

  $ flux account view-job-records -d "> 60" "< 1200"

Both requested duration *and* actual duration can be passed to search for 
certain jobs:

.. code-block:: console

  $ flux account view-job-records -d "< 60" -e "> 30" "< 45"

.. _Flux locally unique ID: https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_19.html

REFERENCES
==========

`RFC 19 - Flux Locally Unique ID (FLUID) <https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_19.html>`_
