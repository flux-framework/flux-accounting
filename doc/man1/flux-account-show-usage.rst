.. flux-help-section: flux account

==========================
flux-account-show-usage(1)
==========================


SYNOPSIS
========

**flux** **account** **show-usage** TABLE --limit=N

DESCRIPTION
===========

.. program:: flux account show-usage

:program:`flux account show-usage` will display a bar chart for the top *N*
associations or the top *N* banks in terms of job usage. A configurable limit
to limit the rows to only the first *N* can be specified with the ``--limit``
optional argument.

.. option:: table

    The table to display job usage data from. The current available options are
    ("associations", "banks").

.. option:: --limit

    The max number of rows to display on the bar graph.

EXAMPLES
--------

.. code-block:: console

    $ flux account show-usage associations --limit=5
    user1 / bankA  | ██████████████████████████████████████████████████████████████  8814977.53
    user2 / bankA  | ██████████████████████████████████████████                      6614967.62
    user3 / bankB  | ██████████████████████                                          4419446.80
    user4 / bankC  | █████████████                                                   3395406.50
    user5 / bankC  | ███████████                                                     3184829.87
