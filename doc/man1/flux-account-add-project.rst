.. flux-help-section: flux account

===========================
flux-account-add-project(1)
===========================


SYNOPSIS
========

**flux** **account** **add-project** PROJECT

DESCRIPTION
===========

.. program:: flux account add-project

:program:`flux account add-project` will add a new project to the
``project_table`` in the flux-accounting database. Associations can reference
these in their `projects` attribute, allowing them to charge specific projects
at job submission.

EXAMPLES
--------

To add a project, just specify a name:

.. code-block:: console

    $ flux account add-project my_project

Then, associations can reference these projects:

.. code-block:: console

    $ flux account add-user --username=user1 --bank=A --projects=my_project
