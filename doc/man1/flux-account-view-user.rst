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
USERNAME). Information about the user can be formatted in JSON or a parsable
format.

.. option:: --parsable

    Prints all information about each association on one line.

.. option:: --json

    Prints all information about each association in JSON format.
