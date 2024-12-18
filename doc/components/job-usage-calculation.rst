.. _job-usage-calculation:

#####################
Job Usage Calculation
#####################

The raw job usage factor :math:`U` for an association is defined as the sum of
products of number of nodes used (``nnodes``) and time elapsed (``t_elapsed``).

:math:`U = sum(n_{nodes} \times t_{elapsed})`

flux-accounting keeps track of job usage for associations using two properties
that are set when the database is first created: **PriorityDecayHalfLife** and
**PriorityUsageResetPeriod**. Each of these parameters represent a number of
weeks by which to hold usage factors up to the time period where jobs no longer
play a role in calculating a usage factor for an association. If these
parameters are not set at database creation, flux-accounting will have a
half-life period of one week and a usage reset period of four weeks, meaning
that jobs become less and less relevant to an association's job usage factor
every week and no longer become part of an association's job usage factor after
four weeks.

The value of **PriorityDecayHalfLife** determines the amount of time that
represents one "usage period" of jobs. flux-accounting then filters out its
``jobs`` table and retrieves an association's jobs that have completed in the
usage period specified. It saves the last seen ``t_inactive`` timestamp in the
``job_usage_factor_table`` for the next query that it runs, which will look for
jobs that have completed after that saved timestamp.

Past usage factors have a decay factor :math:`D` (0.5) applied to them before
they are added to the user's current usage factor.

:math:`U_{past} = (D \times U_{last\_period}) + (D \times D \times U_{period-2}) + ...`

After the current usage factor is calculated, it is written to the first usage
bin in the **job_usage_factor_table** along with the other, older factors. The
oldest factor then gets removed from the table since it is no longer needed.

An example
==========

Let's say an association has the following job records from the most recent
usage period:

.. code-block:: console

    UserID Username  JobID         T_Submit            T_Run       T_Inactive  Nodes
 0    1002 user1002    102 1605633403.22141 1605635403.22141 1605637403.22141      2
 1    1002 user1002    103 1605633403.22206 1605635403.22206 1605637403.22206      2
 2    1002 user1002    104 1605633403.22285 1605635403.22286 1605637403.22286      2
 3    1002 user1002    105 1605633403.22347 1605635403.22348 1605637403.22348      1
 4    1002 user1002    106 1605633403.22416 1605635403.22416 1605637403.22416      1

To calculate the raw usage for this current usage period :math:`U_{current}`,
we extract the nodes and time elapsed from each job:

**total nodes used**:  8

**total time elapsed**:  10000.0

Then, :math:`U_{current}` for ``user1002`` is calculated as:

:math:`U_{current} = (2 \times 2000) + (2 \times 2000) + (2 \times 2000) + (1 \times 2000) + (1 \times 2000)`

:math:`U_{current} = 4000 + 4000 + 4000 + 2000 + 2000 = 16000`

The association's past job usage factors (each one represents a
**PriorityDecayHalfLife** period up to the **PriorityUsageResetPeriod**)
consists of the following:

.. code-block:: console

    username bank  usage_factor_period_0  usage_factor_period_1  usage_factor_period_2  usage_factor_period_3
 0  user1002    C               128.0000               64.00000               64.0000               16.00000

So, the past usage factors have the decay factor :math:`D` applied to them:

:math:`D_{period0} = 128.0 \times 0.5 = 64.0`

:math:`D_{period1} = 64.0 \times 0.5 \times 0.5 = 16.0`

:math:`D_{period2} = 64.0 \times 0.5 \times 0.5 \times 0.5 = 8.0`

:math:`D_{period2} = 16.0 \times 0.5 \times 0.5 \times 0.5 \times 0.5 = 1.0`

The past usage :math:`U_{past}` for ``user1002`` becomes:

:math:`U_{past} = 64.0 + 16.0 + 8.0 + 1.0 = 89`

We then sum the past usage with the current usage to get the historical usage
for ``user1002``, which will be factored in the new fair-share calculation for
the association:

:math:`U_{historical} = U_{current} + U_{past} = 16000.0 + 89.0 = 16089.0`
