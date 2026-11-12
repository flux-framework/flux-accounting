.. _troubleshooting-guide:

#####################
Troubleshooting Guide
#####################

********
Overview
********

This page looks to serve as a resource in case you encounter unusual behavior
from flux-accounting and any of its components. The format of the guide follows
that of a Frequently Asked Questions (FAQ) page, so if you have a suggestion on
a question you'd like to see answered, please consider opening an issue on
`Github <https://github.com/flux-framework/flux-accounting>`_.

**My job is held with a flux-accounting dependency. How can I figure out why
it's held?**

For details on how to interpret flux-accounting dependencies and how they are
resolved, please see the :doc:`../components/limits` page.

**The job-usage values reported for some associations and banks seem
inconsistent and/or inaccurate. How can I resolve this?**

If it seems like association or bank job usage values don't look correct, the
first thing to check is the consistency of the association's ``userid`` in
``association_table``, ``job_usage_factor_table``, and, in periodic decay mode,
``job_usage_per_association_table``. A mismatch in ``job_usage_factor_table``
can prevent completed jobs from being included in usage updates, since jobs
are found by userid and bank.

Run ``flux account sync-userids`` to copy each association's userid into its
existing usage-factor records and periodic usage bins. The command matches
rows by username and bank, and repairs either table even when the other table
already agrees. Usage values, periods, and job timestamps are preserved. For
example, the repair query for periodic bins is:

.. code-block:: sql

  UPDATE job_usage_per_association_table
     SET userid = (
       SELECT a.userid FROM association_table a
        WHERE a.username = job_usage_per_association_table.username
          AND a.bank = job_usage_per_association_table.bank
     )
  WHERE EXISTS (
       SELECT 1 FROM association_table a
        WHERE a.username = job_usage_per_association_table.username
          AND a.bank = job_usage_per_association_table.bank
          AND a.userid != job_usage_per_association_table.userid
  );

The usage-factor repair uses the same query with ``job_usage_factor_table``
in place of ``job_usage_per_association_table``. Rows with no matching
association are left unchanged.

Changing a userid with ``edit-user --userid`` also updates the userid in the
selected associations' existing usage-factor records and periodic usage bins,
so ``sync-userids`` is only needed to repair tables that are already
inconsistent.

.. note::

    This inconsistency between user IDs in the ``association_table`` and
    ``job_usage_factor_table`` was discovered in flux-accounting versions
    prior to ``v0.50.0`` and should be fixed in versions ``v0.50.0`` or later.
    If you are running flux-accounting ``v0.50.0`` (or, more specifically, adding
    associations to the ``association_table``) or later and are still
    running into this bug, please open an issue on GitHub.

**I am getting a "Database is locked" error when trying to read/write from the
flux-accounting DB. How can I resolve this?**

SQLite uses file-level locking to ensure data integrity when multiple processes
access the database simultaneously. A "Database is locked" error usually occurs
when:

- **write lock contention**: Another process holds an exclusive write lock on
  the database file, preventing the operation from proceeding. SQLite allows
  multiple concurrent readers, but only one writer at a time.

- **transaction timeout**: A process started a transaction (with `BEGIN`) but
  hasn't committed or rolled back yet, keeping the lock active longer than
  expected.

- **stale connections**: Processes that crashed or were terminated without
  properly closing their database connections can leave locks in place.

- **NFS or networked filesystems**: SQLite's locking mechanism may not work
  reliably on some network filesystems, leading to lock conflicts.

While the scripts that update job usage and fair-share values for the
flux-accounting database should be quick, a transaction occurring during this
update could cause the database to enter a locked state. To resolve this, try
restarting the flux-accounting service with
``systemctl restart flux-accounting``.
