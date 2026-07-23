.. _multi-factor-priority-plugin:

############################
Multi-Factor Priority Plugin
############################

********
Overview
********

The multi-factor priority plugin (``mf_priority.so``) is a Flux jobtap plugin
that integrates directly with Flux's job manager to perform perform several
critical functions:

- Calculates job priorities using a weighted multi-factor formula
- Enforces resource and job count limits at multiple levels
- Validates user, bank, queue, and project access permissions
- Tracks resource usage and manage job dependencies

The plugin maintains an in-memory representation of the flux-accounting
database and receives periodic updates that adjusts when associations,
banks, queues, or priority factors are added or modified. The plugin is loaded
directly into the job manager process, allowing it to intercept and influence
job lifecycle events in real time.

.. note::
    For details on how to load and configure the plugin, see the
    :doc:`../guide/accounting-guide`.

************
Architecture
************

Integration with Flux Job Manager
=================================

The plugin uses Flux's `jobtap interface`_ to register callbacks at key
points in a job's lifecycle. When a job transitions between states
(NEW → PRIORITY → DEPEND → SCHED → RUN → INACTIVE), the job manager
invokes the corresponding plugin callback, allowing the plugin to:

- Validate job submissions before they enter the system
- Calculate and assign priority values
- Add dependencies to hold jobs when limits are exceeded
- Update resource usage counters
- Release held jobs when resources become available

.. note::

    For more details on job events and lifecycles, see `RFC 21`_.

Auxiliary Data Structures
=========================

The plugin attaches auxiliary data to each job using the jobtap aux
item mechanism:

``mf_priority:bank_info``
    A pointer to the ``Association`` object for the user and bank
    under which the job is running. This structure contains the
    association's fair-share value, resource limits, and current usage
    counters.

``mf_priority:job_info``
    A pointer to a ``Job`` object that stores parsed resource counts
    (e.g., number of nodes and cores) and dependency tracking information.

These aux items are automatically reattached during plugin reload,
allowing the plugin to recover state after a restart.

RPC Interface
=============

The plugin registers several service endpoints under the
``job-manager.mf_priority`` namespace to receive updates from
flux-accounting. These endpoints allow the plugin to receive bulk
updates of association data (users, banks, limits, fair-share values),
queue configurations, project lists, priority factors, and
configuration options. The plugin can also be triggered to
reprioritize all jobs and release held jobs, or to export its internal
state as JSON for inspection.

*************
Configuration
*************

Loading the Plugin
==================

The plugin is typically loaded into the job manager after a Flux instance
is started up:

.. code-block:: console

    $ flux jobtap load path/to/mf_priority.so

With Initial Configuration
==========================

To initialize the plugin with data from the flux-accounting database at
load time, export the database state as JSON and pass it via the
``config`` parameter:

.. code-block:: console

    $ flux jobtap load mf_priority.so \
        config="$(flux account export-json)"

This is the recommended approach for production deployments, as it
ensures the plugin has complete accounting data before processing any
jobs.

TOML Configuration
==================

The plugin can also be configured to load automatically via the job
manager's TOML configuration. Add the following to your Flux instance
configuration:

.. code-block:: toml

    [job-manager.plugins.mf_priority]
    load = "mf_priority.so"

Configuration Options
=====================

``deny_unknown_queues``
    When set to true, the plugin will reject jobs submitted to queues
    that do not exist in the flux-accounting database. When false
    (default), jobs to unknown queues are allowed but receive no
    queue-based priority boost.

This option can be updated at runtime using :man1:`flux-account-edit-config`.

**************
Internal State
**************

The plugin maintains an in-memory representation of the flux-accounting
database using several key data structures:

- A two-level map that stores association information indexed first by
  user ID, then by bank name. Each association contains fair-share values,
  job count and resource limits, current usage counters, priority factors,
  queue access permissions, and a list of any held jobs.

- Stores configuration for each queue, including priority levels, queue-wide
  job limits, and per-association resource limits (both for running jobs and 
  or jobs in the scheduler queue).

- Stores bank-level priority factors that contribute to the priority
  calculation for jobs submitted under each bank.

- The plugin also tracks default bank assignments for users, a list of valid
  projects, current priority factor weights, and configuration flags.

*************
Job Lifecycle
*************

The plugin intercepts jobs at multiple points during their lifecycle.
Understanding this sequence is essential for troubleshooting job
behavior and limit enforcement.

``job.validate``
================

When a job is submitted, ``validate_cb()`` runs before the job is
accepted into the system. This callback:

1. Verifies the user ID exists in the flux-accounting database
2. Determines which bank the job should run under (explicit jobspec
   attribute, user's default bank, or falls back to the user ID)
3. Validates the user has an active association in that bank
4. Validates the job's queue (if specified) exists and is accessible
5. Validates the job's project (if specified) exists
6. Checks the association has not exceeded their ``max_active_jobs`` limit
7. Validates job size against queue and association resource limits

If validation fails, the job is rejected with a descriptive error
message.

``job.new``
===========

``new_cb()`` runs after a job enters the system. This callback:

1. Creates or retrieves the ``Association`` object for the job
2. Attaches the association as auxiliary data (``mf_priority:bank_info``)
3. Updates the jobspec with default bank/project if not specified
4. Increments the association's ``cur_active_jobs`` counter

.. note::

    For jobs that were already running (e.g., after a plugin reload),
    the plugin will re-increment running counters and resource usage.

``job.state.priority``
======================

``priority_cb()`` calculates the job's integer priority. This callback:

1. Calls ``priority_calculation()`` to compute the weighted priority for the
   job
2. Posts the job's fair-share value to a memo event for visibility in
   :man1:`flux-account-jobs`

.. note::

   For jobs whose association data is missing (like in a plugin reload
   scenario), the plugin assigns a minimal priority until data arrives.

For details on the priority calculation formula, see :doc:`job-priorities`.

``job.state.depend``
====================

``depend_cb()`` enforces resource and job count limits by adding named
dependencies to jobs that would otherwise exceed configured thresholds. The
plugin enforces a number of different limit types:

Queue Limits
------------

max running jobs
    Added when the number of running jobs in the queue would exceed the
    ``max_running_jobs`` limit for a queue

max jobs in SCHED state
    Added when the number of SCHED-state jobs in the queue would exceed
    the ``max_sched_jobs`` limit for a queue

max nodes in SCHED state for an association
    Added when the association's node count in SCHED state in this queue
    would exceed the ``max_sched_nodes_per_assoc`` limit for a queue

max cores in SCHED state for an association
    Added when the association's core count in SCHED state in this queue
    would exceed the ``max_sched_cores_per_assoc`` limit for a queue

max resources in RUN state for a given association
    Added when the number of nodes across all of an association's running jobs
    would exceed the ``max_nodes_per_assoc`` limit for a queue

Association Limits
------------------

max running jobs
    Added when the association would exceed their ``max_run_jobs`` limit

max jobs in SCHED state
    Added when the association would exceed their ``max_sched_jobs`` limit

max resources in RUN state for a given association
    Added when the association's resource usage would exceed either their
    ``max_nodes`` or ``max_cores`` limits

When any dependency is added, the job is recorded in the association's
``held_jobs`` vector for later release.

.. note::
    For more details on limit types and their behavior, see
    :doc:`limits`.

``job.state.sched``
===================

``sched_cb()`` runs when a job transitions to SCHED state (ready for
scheduling). This callback:

1. Increments the association's ``cur_sched_jobs`` counter
2. Updates per-queue SCHED node and core counts

These counters are used to enforce SCHED-state-specific limits.

``job.state.run``
=================

``run_cb()`` runs when a job begins execution. This callback:

1. Increments current running jobs, current nodes, and current core counters
   for the association
2. Calls ``check_and_release_held_jobs()`` to release any waiting jobs that
   have potentially cleared all dependencies

``job.state.inactive``
======================

``inactive_cb()`` runs when a job completes or is cancelled. This
callback:

1. Decrements active, running job counters, and currently-allocated
   resource usage for the association
2. Calls ``check_and_release_held_jobs()`` to release any waiting jobs that
   have potentially cleared all dependencies

Job Updates
===========

The plugin supports updating a job's bank or queue after submission via
``update_bank_cb()`` and ``update_queue_cb()``. These callbacks:

1. Validate the new bank/queue is accessible
2. Verify the new bank has capacity to accept the job
3. Apply the update and recalculate priority

*****************
Limit Enforcement
*****************

When a job would exceed a configured limit, the plugin adds a named
dependency to the job. The job remains in ``DEPEND`` state and does not
proceed to the scheduler until all dependencies are removed.

Each dependency name corresponds to a specific limit type (e.g.,
``D_QUEUE_MRJ`` for queue max running jobs). This fine-grained naming
allows the plugin to selectively release jobs as different limits are
satisfied.

The ``check_and_release_held_jobs()`` function is called in more than one
callback throughout a job's lifecycle. This function:

1. Iterates through the association's ``held_jobs`` vector
2. For each held job, checks each of its dependencies individually and removes
   them if the associated limit is no longer reached
3. Releases jobs when all of its dependencies are cleared

The release mechanism maintains approximate FIFO ordering within the
held jobs list, but prioritizes releasing jobs that have all dependencies
satisfied.

Interaction with SCHED Limits
=============================

Some limits apply specifically to jobs in SCHED state. These limits prevent
associations from flooding the scheduler queue, which could starve other users
even if resource limits are not yet reached.

Jobs held by SCHED-state limits will be released as other jobs in SCHED state
begin running or are cancelled.

********************
Priority Calculation
********************

The plugin calculates job priority using a weighted multi-factor
formula that considers the association's current fair-share value and optional
and configurable factors according to the bank they belong to or the queue
they are submitting the job to. For detailed examples and instructions on
customizing priority calculation, see :doc:`job-priorities`. For information
on how fair-share values are computed, see :doc:`fair-share`.

************************
Plugin Reload & Recovery
************************

Handling Plugin Reload or Missing Data
======================================

When the plugin is reloaded (e.g., after a Flux restart or explicit
``flux jobtap remove`` / ``flux jobtap load``), it must reconstruct its
view of active jobs. The jobtap interface helps by:

1. Invoking callbacks for existing jobs in reverse state order (INACTIVE
   → RUN → SCHED → DEPEND → PRIORITY → NEW)
2. Allowing the plugin to reattach aux items to jobs

The plugin detects reload scenarios by checking for missing aux items
and handles them gracefully. Jobs missing association data are assigned to a
temporary "DNE" (does not exist) bank that will prevent it from running. When
accounting data arrives via RPC, these held jobs are then updated with their
correct association, and aux items are reattached as jobs are processed. This
ensures that jobs are not blocked indefinitely if accounting data is slow to
load.

***************
Troubleshooting
***************

Querying Plugin State
=====================

To inspect the plugin's internal state, use ``flux jobtap query``:

.. code-block:: console

    $ flux jobtap query mf_priority.so

This outputs a JSON representation of the plugin's state, including:

- All associations
- Queue configurations
- Bank priorities
- Priority factor weights
- Configuration options

Checking Job Dependencies
=========================

If a job is stuck in DEPEND state, check which dependencies are holding
it:

.. code-block:: console

    $ flux jobs -o '{id} {dependencies}' <jobid>

Verifying Priority Calculation
===============================

To see how a job's priority was calculated, use
:man1:`flux-account-jobs`:

.. code-block:: console

    $ flux account jobs <username>

This shows a breakdown of each factor's contribution to the final
priority.

.. _RFC 21: https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_21.html

.. _jobtap interface: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man7/flux-jobtap-plugins.html
