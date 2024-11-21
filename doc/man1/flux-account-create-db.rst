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

   The number of weeks at which job usage information gets reset to 0. By
   default, the usage reset period is set at 4 weeks.

.. option:: --priority-decay-half-life

    The contribution of historical usage in weeks on the composite job usage
    value. By default, this is set at 1 week.
