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
first thing to check would be the consistency between the association's
``userid`` column in both the ``association_table`` and the
``job_usage_factor_table``. If they are reporting different values, then the
script that updates job usage values for that association will be skipped
since the script searches for completed jobs based on ``userid``. To sync the
two tables to use the same user ID defined in the ``association_table`` in the
``job_usage_factor_table``, you can run the ``sync-userids`` command. Under the
hood, this command is running this query to see which user IDs are
inconsistent:

.. code-block:: sql

  SELECT j.username,
         j.userid AS old_userid,
         a.userid AS new_userid
    FROM job_usage_factor_table j
    JOIN association_table a
      ON j.username = a.username
   WHERE j.userid != a.userid;

And this one to update ``job_usage_factor_table`` with the user ID found in
``association_table``:

.. code-block:: sql

  UPDATE job_usage_factor_table
     SET userid = (
       SELECT association_table.userid
         FROM association_table
        WHERE association_table.username = job_usage_factor_table.username
     )
  WHERE EXISTS (
       SELECT 1
         FROM association_table
        WHERE association_table.username = job_usage_factor_table.username
  );

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
