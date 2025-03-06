.. _sanity-checklist:

#######################################
Flux Accounting Health/Sanity Checklist
#######################################

********
Overview
********

As flux-accounting is deployed and running on a system, there are a number of
components an administrator can check to ensure that the module is loaded and
running as expected. The following attempts to list the major tasks an
administrator can look to complete after building, installing, and configuring
flux-accounting on a system.

*****************************
Database Integrity and Access
*****************************

Ensure users, banks, queues, and projects can be added, viewed, and edited with
various ``flux account`` commands:

.. code-block:: console

    $ flux account add-bank --parent-bank=root giants 1
    $ flux account add-user --username=crawford --bank=giants
    $ flux account add-queue orange
    $ flux account add-projects shortstops

Conversely, they can be removed and/or deactivated with their respective
``delete-*`` commands.

If the database is populated, ensure banks and associations are returned when
viewing the entire hierarchy with
``flux account view-bank <root_bank> --tree``.

***************************************************
Multi-Factor Priority Plugin Load and Configuration
***************************************************

Check that the multi-factor priority plugin is loaded:

.. code-block:: console

    $ flux jobtap list

    mf_priority.so

And flux-accounting information has been successfully sent to the plugin with
``flux account-priority-update``. You can confirm what flux-accounting data has
been loaded by looking at the output of ``flux jobtap query``:

.. code-block:: console

    $ flux jobtap query mf_priority.so >query.json

If the plugin is loaded, you can check that it is correctly annotating jobs
with bank and project names in the job's ``jobspec`` or ``eventlog``:

.. code-block:: console

    $ flux job info job_id eventlog

    {"timestamp":1741284758.3611979,"name":"submit","context":{"userid":5035,"urgency":16,"flags":0,"version":1}}
    {"timestamp":1741284758.374285,"name":"jobspec-update","context":{"attributes.system.bank":"giants","attributes.system.project":"shortstops"}}
    {"timestamp":1741284758.3743033,"name":"validate"}
    {"timestamp":1741284758.3878355,"name":"depend"}
    {"timestamp":1741284758.3878522,"name":"priority","context":{"priority":50000}}
    {"timestamp":1741284758.3889365,"name":"alloc","context":{"annotations":{"sched":{"resource_summary":"rank0/core0"}}}}
    {"timestamp":1741284758.3902109,"name":"start"}

*************************
``jobs`` Table Population
*************************

After jobs have been submitted, run, and completed, they should be populated
into the ``jobs`` table in the flux-accounting DB with
``flux account-fetch-job-records``. You can check that these jobs are showing
up and being factored into job usage and fair-share values for associations:

.. code-block:: console

    $ flux account view-job-records --user=crawford

    jobid           | username | userid   | t_submit        | nnodes   | project    | bank
    18320719872     | crawford | 5035     | 1741285811.09   | 1        | shortstops | giants

*******
Summary
*******

flux-accounting is comprised of a number of different components that work
together to create a robust and flexible accounting system for the Flux
resource manager. It is important to check that the various pieces of
flux-accounting (the SQLite database, the priority plugin, and the different
scripts to update job-usage and fair-share values for associations) are
up and running to maintain the integrity and accuracy of the accounting system.
Ensuring these components are functioning properly helps prevent discrepancies
in limit enforcement, maintains fair-share calculations, and supports efficient
and fair job scheduling within the Flux resource manager.
