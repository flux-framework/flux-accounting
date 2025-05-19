.. flux-help-section: flux account

==============================
flux-account-delete-project(1)
==============================

SYNOPSIS
========

**flux** **account** **delete-project** PROJECT

DESCRIPTION
===========

.. program:: flux account delete-project

:program:`flux account delete-project` will remove a project from the
``project_table`` in the flux-accounting database. Note that removing a project
from this table will not automatically remove any references to this project
elsewhere in the flux-accounting DB, particularly the ``association_table``.
If associations still reference this project, a ``WARNING`` message will be
returned reminding the user to also remove this project from all associations'
rows.
