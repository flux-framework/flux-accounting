.. flux-help-section: flux account

=========================
flux-account-create-db(1)
=========================


SYNOPSIS
========

**flux** **account** **create-db** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account create-db

:program:`flux account create-db` creates the flux-accounting SQLite database
which will hold all of the accounting information for users, banks, queues,
projects, and job records.

.. option:: --priority-usage-reset-period

   The amount of time (in Flux Standard Duration or in seconds) in which job
   usage gets reset to 0. By default, this is set at 4 weeks.

.. option:: --priority-decay-half-life

   The contribution of historical usage in the amount of time (in Flux
   Standard Duration or in seconds) on the composite usage value. By default,
   this is set at 1 week.

.. option:: --decay-factor

   The amount of decay to apply to historical usage. By default, this is set at
   0.5.
