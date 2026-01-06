.. flux-help-section: flux account

=================================
flux-account-view-usage-report(1)
=================================

SYNOPSIS
========

**flux** **account** **view-usage-report** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account view-usage-report

:program:`flux account view-usage-report` generates a job usage report to
``stdout`` for a user, bank, or association that can be customized with various
options: 

.. option:: -s/--start=DATE

    Start time for usage. The timestamp can be in seconds-since-epoch or a
    human readable timestamp (e.g. ``'01/01/2025'``, ``'2025-01-01 08:00:00'``,
    ``'Jan 1, 2025 8am'``).

.. option:: -e/--end=DATE

    End time for usage. The timestamp can be in seconds-since-epoch or a
    human readable timestamp (e.g. ``'01/01/2025'``, ``'2025-01-01 08:00:00'``,
    ``'Jan 1, 2025 8am'``).

.. option:: -u/--username=USERNAME

    Only calculate usage for USERNAME.

.. option:: -b/--bank=BANK

    Only calculate usage for BANK.

.. option:: -r/--report-type=bybank|byuser|byassociation

    Specify how data should be binned.

.. option:: -t/--time-unit=hour|min|sec

    Specify time unit for data.

.. option:: -S/--job-size-bins=NNODES,NNODES,...

    Bin by job sizes.

EXAMPLES
--------

Passing different options for ``-t/--time-unit`` will change how usage is
represented:

.. code-block:: console

  $ flux account view-usage-report -u u1 -t sec
  bankuser(nodesec)           total
  A:50001                          540.00
  TOTAL                            540.00

  $ flux account view-usage-report -u u1 -t min
  bankuser(nodemin)           total
  A:50001                            9.00
  TOTAL                              9.00

  $ flux account view-usage-report -u u1 -t hour
  bankuser(nodehour)          total
  A:50001                            0.15
  TOTAL                              0.15

Job size bins can further categorize job usage:

.. code-block:: console

  $ flux account view-usage-report -u u1 -S 1,2,3,4
  bankuser(nodesec)                    1+             2+             3+             4+
  A:50001                          180.00         120.00           0.00         240.00
  TOTAL                            180.00         120.00           0.00         240.00 
