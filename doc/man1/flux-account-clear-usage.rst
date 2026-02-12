.. flux-help-section: flux account

===========================
flux-account-clear-usage(1)
===========================


SYNOPSIS
========

**flux** **account** **clear-usage** [BANK BANK ...] [OPTIONS]

DESCRIPTION
===========

.. program:: flux account clear-usage

:program:`flux account clear-usage` will reset the usage for one or more banks
and all of the users under those banks back to 0.

.. option:: --ignore-older-than

    A timestamp to which older jobs will be ignored when calculating job
    usage; accepts multiple formats: seconds since epoch timestamp or human
    readable timestamp (e.g. ``01/01/2025``, ``2025-01-01 08:00:00``, ``Jan 1,
    2025 8am``)
