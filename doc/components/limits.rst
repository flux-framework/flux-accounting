.. _limits:

######
Limits
######

********
Overview
********

The multi-factor priority plugin in flux-accounting not only performs
validation for associations and priority calculation for jobs; it can also
administer and enforce limits on a per-association and per-queue basis. Limits
are another way to ensure fair behavior of systems that see a lot of
simultaneous activity from a large number of users.

Hard Limits vs. Soft Limits
===========================

There are two different kinds of limits in flux-accounting: **hard limits** and
**soft limits**. Hard limits will prevent an association from submitting a job
altogether and will report a message as to why the job cannot proceed past
validation. Soft limits will allow a job to be submitted but will prevent it
from running until a prerequisite has been met.

There is just one hard limit in flux-accounting:

(per-association) max active jobs
  The max number of active jobs an association can have at any given time.

The soft limits in flux-accounting are composed of:

(per-association) max running jobs
  The max number of running jobs an association can have at any given time.

(per-association) max resources
  The max number of resources (total cores + total nodes) an association can
  have across their running jobs at any given time.

(per-queue) max running jobs
  The max number of running jobs an association can have in a given queue at
  any given time.

(per-queue) max nodes
  The max number of nodes an association can have across their running jobs in
  a givent queue at any given time.

.. note::
    For more details on the difference between an active job and a running job,
    see the `virtual states`_ section of RFC 21.

An example
==========

The difference between hard and soft limits might be best described by example.
Let's configure an association to have a limit configuration of at most 1
running job and 2 active jobs:

.. code-block:: console

    $ flux account add-user --username=buster --bank=giants --max-running-jobs=1 --max-active-jobs=2

``buster`` can submit a job and the priority plugin will generate a priority
for this job and pass it on to the scheduler to begin running. If ``buster``
submits a second job while the first one is running, this second job will be
held until the first job completes. Specifically, a dependency_ will be added
to the job to hold it in the ``DEPEND`` state until the first job has
transitioned to the ``INACTIVE`` state. The name of the dependency can be found
in the job's eventlog:

.. code-block:: console

    $ flux job eventlog JOBID
    dependency-add description="max-resources-user-limit"

After the first job has transitioned to ``INACTIVE``, the dependency will be
removed and the job can proceed to have its priority calculated and move on to
the scheduler to be run:

.. code-block:: console

    dependency-remove description="max-resources-user-limit"
    depend
    priority priority=50000
    alloc annotations={"sched":{"resource_summary":"rank0/core[0-1]"}}

If ``buster`` submits a *third* job while the first job is still running and
the second job is waiting in ``DEPEND``, it will be rejected due to the
association's max active jobs limit:

.. code-block:: console

    $ flux submit my_job
    flux-job: user has max active jobs

These limits can be configured and modified after an association or a queue
has been created in flux-accounting with the ``edit-user`` and ``edit-queue``
commands. After modifying limits for either an association or a queue, be sure
to update the priority plugin with the new data written to the flux-accounting
database:

.. code-block:: console

    $ flux account-priority-update

.. _virtual states: https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_21.html#virtual-states

.. _dependency: https://flux-framework.readthedocs.io/projects/flux-core/en/latest/guide/troubleshooting.html#job-dependencies
