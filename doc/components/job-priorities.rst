.. _job-priorities:

##############
Job Priorities
##############

********
Overview
********

Job priorities in flux-accounting are an integer value that represent how
important a job is. Priorities can range from 0 to 4294967295, where the higher
the number, the higher the priority the job is. Priorities are calculated as a
result of a number of different factors that all play a varying level of
importance. In this document, we will explain the factors that contribute to
the calculation of a job's priority as well as how to customize how job
priority is calculated.

************************
The Priority Calculation
************************

As mentioned in the :doc:`../guide/accounting-guide`, the priority plugin
generates an integer priority for incoming jobs using a number of factors. Each
factor :math:`F` has an associated integer weight :math:`W` that determines its
importance in the overall priority calculation. A job's priority :math:`P` can
be represented as:

.. math::

  P = (F_{fairshare} \times W_{fairshare})
      + (F_{queue} \times W_{queue})
      + (F_{bank} \times W_{bank})
      + ((F_{urgency} - 16) \times W_{urgency})

The current factors represented in the priority equation described above are:

fair-share
  The ratio between the amount of resources allocated vs. resources
  consumed. See the :ref:`Glossary definition <glossary-section>` for a more
  detailed explanation of how fair-share is utilized within flux-accounting.

queue
  A configurable factor assigned to a queue.

bank
  A configurable factor assigned to a bank.

urgency
  A user-controlled factor to prioritize their own jobs.

Each of these factors can be configured with a custom weight to increase their
relevance to the final calculation of a job's integer priority. By default,
each factor has the following weight:

+------------+---------+
| factor     | weight  |
+============+=========+
| fair-share | 100000  |
+------------+---------+
| queue      | 10000   |
+------------+---------+
| bank       | 0       |
+------------+---------+
| urgency    | 1000    |
+------------+---------+

These can be modified to change how a job's priority is calculated. For
example, if you wanted the queue to be more of a factor than fair-share, you
can adjust each factor's weight accordingly:

.. code-block:: console

    $ flux account edit-factor --factor=fairshare --weight=1000
    $ flux account edit-factor --factor=queue --weight=100000
    $ flux account edit-factor --factor=bank --weight=500
    $ flux account-priority-update

An example
==========

Let's say an association is running a job for the first time to a queue and
bank that have no effect on the job's priority. Then, the calculation for this
job's priority becomes very straightforward:

.. math::

    P = (F_{fairshare} \times W_{fairshare})
      + (F_{queue} \times W_{queue})
      + (F_{bank} \times W_{bank})
      + (W_{urgency} \times (F_{urgency} - 16))

.. math::
    P = (0.5 \times 100000)
      + (0 \times 10000)
      + (0 \times 0)
      + (1000 \times (16 - 16))

.. math::
    P = 50000 + 0 + 0 + 0

.. math::
    P = 50000

As the association continues to submit more jobs and their (along with other
members of their bank) usage of the system increases, their fair-share value
will reflect this usage and positively or negatively affect future job
priorities.

.. note::
    For a more detailed description on how fair-share is calculated, see
    :doc:`fair-share`.

**********************************
Configuring Other Priority Factors
**********************************

To further refine how other factors, such as the bank and/or queue the
association is submitting jobs under, contribute to a job's resulting priority,
specific priority values can be assigned to each individual bank and/or queue.

An example
==========

Let's create the following flux-accounting bank hierarchy: below the ``root``
bank there are three sub banks which hold associations: ``A``, ``B``, and
``C``:

.. code-block:: text

    root
    ├── A
    │   ├── user1
    │   └── user2
    ├── B
    │   ├── user3
    │   └── user4
    └── C
        ├── user2
        └── user5

And each bank is configured to have a different priority associated with it,
where bank ``A`` is the most important and bank ``C`` is the least important:

.. code-block:: console

    $ flux account edit-bank A --priority=300
    $ flux account edit-bank B --priority=100
    $ flux account edit-bank C --priority=-5

And the ``bank`` factor is configured to have a weight :math:`> 0`:

.. code-block:: console

    $ flux account edit-factor --factor=bank --weight=10

If ``user2`` has equivalent fair-share values in both banks ``A`` and ``C`` and
submits jobs under both banks, each job will end up with significantly
different priorities:

.. math::
    P_{job\_A} = (0.5 \times 100000)
      + (0 \times 10000)
      + (300 \times 10)
      + (1000 \times (16 - 16))

.. math::
    P_{job\_A} = 50000 + 0 + 3000 + 0

.. math::
    P_{job\_A} = 53000

.. math::
    P_{job\_C} = (0.5 \times 100000)
      + (0 \times 10000)
      + (300 \times -5)
      + (1000 \times (16 - 16))

.. math::
    P_{job\_C} = 50000 + 0 - 1500 + 0

.. math::
    P_{job\_C} = 48500

The same principle can be configured to queues, resulting in a multivariate
equation that considers multiple factors when calculating the priority for a
job.

**********************
Viewing Job Priorities
**********************

On a system with many associations, banks, and queues, it could become
difficult and somewhat tedious to have to reverse engineer how a priority for a
particular job has been calculated, especially if flux-accounting has been
running for an extended period of time, associations have weeks worth of usage
contributing to their fair-share values, some banks are getting more usage than
others, etc. So, flux-accounting provides a way to view a breakdown of the way
a job's priority was calculated on the command line.

``flux account jobs`` will output a breakdown of the various components that
factored into a job's priority for a given user. Options can be passed to filter
jobs submitted under a particular bank or a particular queue.

.. note::
    For more details on usage of the ``flux account jobs`` command, see
    :man1:`flux-account-jobs`.

An example
==========

Let's imagine a flux-accounting database configured to have an association
``bonds`` submitting a job under a bank ``A`` with priority :math:`100` and
queue ``bronze`` with priority :math:`1`. In this scenario, banks are
configured to contribute to a job's priority calculation with a factor of
:math:`1000`. So, the job priority calculation for a job :math:`P` becomes:

.. math::

    P = (F_{fairshare} \times 100000)
      + (F_{queue} \times 10000)
      + (F_{bank} \times 1000)
      + (1000 \times (F_{urgency} - 16))
  
To view a breakdown of this job's priority, simply run
``flux account jobs bonds``:

.. code-block:: console

    $ flux account jobs bonds
    JOBID          USER     BANK    BANKPRIO  BANKFACT  QUEUE   QPRIO  QFACT  FAIRSHARE FSFACTOR  URGENCY URGFACT PRIORITY
    fnYtwBV        bonds    A       100.0     1000      bronze  1      10000  0.5       100000    16      1000    160000 

.. warning::
    Changing priority factor weights could result in inaccurate breakdowns of
    job priorities that were calculated using different factor weights (such as
    jobs that have already been submitted and are running or jobs that have
    already completed). This is because the ``jobs`` command pulls the *latest*
    factor weights from the flux-accounting database, which could have been
    updated since the time a job was submitted.
