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

See :man1:`flux-account-create-db` for more details.

pop-db
^^^^^^

Populate a flux-accounting database with ``.csv`` files.

See :man1:`flux-account-pop-db` for more details.

export-db
^^^^^^^^^

Export a flux-accounting database into ``.csv`` files.

See :man1:`flux-account-export-db` for more details.

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

Deactivate an association in the flux-accounting database.

See :man1:`flux-account-delete-user` for more details.

edit-user
^^^^^^^^^

Modify an attribute for an association in the flux-accounting database.

See :man1:`flux-account-edit-user` for more details.

BANK ADMINISTRATION
===================

view-bank
^^^^^^^^^

View information about a bank in the flux-accounting database.

See :man1:`flux-account-view-bank` for more details.

add-bank
^^^^^^^^

Add a bank to the flux-accounting database.

See :man1:`flux-account-add-bank` for more details.

delete-bank
^^^^^^^^^^^

Deactivate a bank in the flux-accounting database.

See :man1:`flux-account-delete-bank` for more details.

edit-bank
^^^^^^^^^

Modify an attribute for a bank in the flux-accounting database,

See :man1:`flux-account-edit-bank` for more details.

list-banks
^^^^^^^^^^

List all of the banks in the ``bank_table``.

See :man1:`flux-account-list-banks` for more details.

QUEUE ADMINISTRATION
====================

view-queue
^^^^^^^^^^

View information about a queue in the flux-accounting database.

See :man1:`flux-account-view-queue` for more details.

add-queue
^^^^^^^^^

Add a queue to the flux-accounting database.

See :man1:`flux-account-add-queue` for more details.

delete-queue
^^^^^^^^^^^^

Remove a queue from the flux-accounting database.

See :man1:`flux-account-delete-queue` for more details.

edit-queue
^^^^^^^^^^

Edit a queue's properties in the flux-accounting database.

See :man1:`flux-account-edit-queue` for more details.

list-queues
^^^^^^^^^^^

List all defined queues in the flux-accounting database.

See :man1:`flux-account-list-queues` for more details.

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
