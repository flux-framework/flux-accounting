.. flux-help-section: flux account

=================================
flux-account-estimate-priority(1)
=================================

SYNOPSIS
========

**flux** **account** **estimate-priority** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account estimate-priority

:program:`flux account estimate-priority` estimates the priority a job would
receive from the loaded multi-factor priority plugin without submitting a job.
The estimate is calculated for the authenticated caller using the plugin's
current in-memory accounting data.

By default, the command estimates priority for the caller's default bank. Use
``--bank`` to select a specific bank, or ``--all-banks`` to estimate priority
for each of the caller's bank associations.

The estimate is a real-time value. It is susceptible to briefly lagging the
SQLite database until a regular accounting update is pushed to the plugin, and
it does not predict wait time or account for submission limits, resource
requests, or scheduling conditions. If ``--queue`` is omitted and Flux has a
configured default queue, that queue is used for the estimate. If Flux has no
configured default queue, the estimate is calculated with no queue factor. In
JSON output, this no-queue case is represented as ``"queue": null``.

.. option:: --bank=BANK

    Estimate priority under BANK. This option cannot be combined with
    ``--all-banks``.

.. option:: --all-banks

    Estimate priority under every bank association for the caller. Disabled
    associations or bank-specific queue errors are included as rows with an
    ``ERROR`` value.

.. option:: --queue=QUEUE

    Estimate priority under QUEUE. If this option is omitted, the Flux default
    queue is used when one is configured. If no Flux default queue is found,
    the estimated job has no queue factor.

.. option:: --urgency=N

    Estimate priority with urgency N. The default is ``16``. Values in the
    Flux urgency range ``0`` through ``31`` are accepted, but values above
    ``16`` require instance-owner credentials.

.. option:: --json

    Output estimates as a JSON array. Each row contains ``bank``, ``queue``,
    ``urgency``, ``priority``, and ``error``. Successful estimates have
    ``error: null``; ineligible rows have ``priority: null``. A ``queue`` value
    of ``null`` means no queue affected the estimated priority.

EXIT STATUS
===========

The command exits successfully if at least one estimate is calculated. It exits
nonzero if the request is invalid, the plugin cannot estimate priority, or all
returned rows contain errors.
