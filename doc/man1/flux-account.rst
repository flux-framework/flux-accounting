.. flux-help-section: flux account

===============
flux-account(1)
===============


SYNOPSIS
========

**flux** **account** [*COMMAND*] [OPTIONS]

DESCRIPTION
===========

.. program:: flux account

:program:`flux account` provides an interface to the SQLite database containing
information regarding banks, associations, queues, projects, and archived jobs.
It also provides administrative commands like exporting and populating the DB's
information to and from ``.csv`` files, updating the database when new versions
of flux-accounting are released, and more.

DATABASE ADMINISTRATION
=======================

create-db
^^^^^^^^^

Create the flux-accounting database.

See flux account-create-db(1) for more details.

pop-db
^^^^^^

Populate a flux-accounting database with ``.csv`` files.

See flux account-pop-db(1) for more details.

export-db
^^^^^^^^^

Export a flux-accounting database into ``.csv`` files.

See flux account-export-db(1) for more details.

USER ADMINISTRATION
===================

view-user
^^^^^^^^^

View information about an association in the flux-accounting database.

See :man1:`flux-account-view-user` for more details.

add-user
^^^^^^^^

Add an association to the flux-accounting database.

See :man1:`flux-account-add-user` for more details.

delete-user
^^^^^^^^^^^

Set an association to inactive in the flux-accounting database.

See :man1:`flux-account-delete-user` for more details.

edit-user
^^^^^^^^^

Modify an attribute for an association in the flux-accounting database.

See :man1:`flux-account-edit-user` for more details.

BANK ADMINISTRATION
===================

view-bank
^^^^^^^^^

add-bank
^^^^^^^^

delete-bank
^^^^^^^^^^^

edit-bank
^^^^^^^^^

list-banks
^^^^^^^^^^

QUEUE ADMINISTRATION
====================

view-queue
^^^^^^^^^^

add-queue
^^^^^^^^^

delete-queue
^^^^^^^^^^^^

edit-queue
^^^^^^^^^^

PROJECT ADMINISTRATION
======================

view-project
^^^^^^^^^^^^

add-project
^^^^^^^^^^^

delete-project
^^^^^^^^^^^^^^

list-projects
^^^^^^^^^^^^^

JOB RECORDS
===========

view-job-records
^^^^^^^^^^^^^^^^

update-usage
^^^^^^^^^^^^

scrub-old-jobs
^^^^^^^^^^^^^^
