.. flux-help-section: flux account

=========================
flux-account-view-user(1)
=========================


SYNOPSIS
========

**flux** **account** **view-user** USERNAME [OPTIONS]

DESCRIPTION
===========

.. program:: flux account view-user

:program:`flux account view-user` returns all of the various attributes for
every bank that a user belongs to (i.e every **association** that contains
USERNAME). Information about the user can be formatted in a parsable format as
well as customizing which fields are returned.

.. option:: --parsable

    Prints all information about each association on one line.

.. option:: --fields

    Customize which fields are returned in the output of ``view-user``.

.. option:: --list-banks

    Concisely list all of the banks a user belongs to.

.. option:: -o/--format

    Specify output format using Python's string format syntax.

.. option:: -j/--job-usage

    List all of the past job usage factors that make up an association's
    historical job usage value.

    .. note::
        This optional argument cannot be combined with ``--fields``.
