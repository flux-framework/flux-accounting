.. _job-usage-calculation:

#####################
Job Usage Calculation
#####################

The raw job usage factor for an association is defined as the sum of products
of number of nodes used (``nnodes``) and time elapsed (``t_elapsed``). To
calculate the raw usage for a given association *U*:


:math:`U = sum(nnodes \times t\_elapsed)`

flux-accounting keeps track of job usage in a table according to two properties
that are set when the database is first created: **PriorityDecayHalfLife** and
**PriorityUsageResetPeriod**. Each of these parameters represent a number of
weeks by which to hold usage factors up to the time period where jobs no longer
play a factor in calculating a usage factor. If these options aren't specified,
the table defaults to 4 usage columns, each which represent one week's worth of
jobs.

The **job usage factor** table stores past job usage factors per association.
When an association is first added to the **association** table, they are also
added to **job usage factor** table.

The value of **PriorityDecayHalfLife** determines the amount of time that
represents one "usage period" of jobs. flux-accounting filters out its ``jobs``
table and retrieves an association's jobs that have completed in the usage
period.

As time goes on and usage periods get older, their raw usage value has a decay
factor :math:`D` (0.5) applied to them before they are added to the user's
current raw usage factor.

:math:`U_{past} = (D \times U_{last\_period}) + (D \times D \times U_{period-2}) + ...`

After the current usage factor is calculated, it is written to the first usage
bin in the **job usage factor** table along with the other, older factors. The
oldest factor then gets removed from the table since it is no longer needed.

An example
==========

Let's say an association has the following job records from the most recent
**PriorityDecayHalfLife**:

.. code-block:: console

    UserID Username  JobID         T_Submit            T_Run       T_Inactive  Nodes                                                                               R
 0    1002     1002    102 1605633403.22141 1605635403.22141 1605637403.22141      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
 1    1002     1002    103 1605633403.22206 1605635403.22206 1605637403.22206      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
 2    1002     1002    104 1605633403.22285 1605635403.22286 1605637403.22286      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
 3    1002     1002    105 1605633403.22347 1605635403.22348 1605637403.22348      1  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
 4    1002     1002    106 1605633403.22416 1605635403.22416 1605637403.22416      1  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}

**total nodes used**:  8

**total time elapsed**:  10000.0

:math:`U_{user1002\_current}` is calculated as:

:math:`U_{user1002\_current} = (2 \times 2000) + (2 \times 2000) + (2 \times 2000) + (1 \times 2000) + (1 \times 2000)`

:math:`U_{user1002\_current} = 4000 + 4000 + 4000 + 2000 + 2000`

:math:`U_{user1002\_current} = 16000`

And the association's past job usage factors (each one represents a
**PriorityDecayHalfLife** period up to the **PriorityUsageResetPeriod**)
consists of the following:

.. code-block:: console

    username bank  usage_factor_period_0  usage_factor_period_1  usage_factor_period_2  usage_factor_period_3
 0  user1002    C               128.0000               64.00000               64.0000               16.00000

The past usage factors have the decay factor applied to them:
``[64.0, 16.0, 8.0, 1.0]``

:math:`U_{user1002\_past} = 64.0 + 16.0 + 8.0 + 1.0 = 89`

:math:`U_{user1002\_historical} = U_{user1002\_current} + U_{user1002\_past} = 16000.0 + 89.0 = 16089.0`

:math:`U_{user1002}`'s job usage value now becomes :math:`16089.0`, which takes
into account both their most recent *and* historical job usage.


Viewing Breakdowns of Historical Job Usage
==========================================

Since an association's historical job usage (i.e. the value reported in the
``job_usage`` column) is comprised of potentially multiple usage factors that
make up an association's job usage value, it would be useful to see how this
value is calculated. The ``view-user`` command offers a ``-J/--job-usage``
optional argument, which will return all of the association's job usage columns
that make up their historical job usage value:

.. code-block:: console

    $ flux account view-user --parsable -J moussa
    username | userid | bank     | usage_factor_period_0 | usage_factor_period_1 | usage_factor_period_2 | usage_factor_period_3
    ---------+--------+----------+-----------------------+-----------------------+-----------------------+----------------------
    moussa   | 12345  | A        | 100.0                 | 243.5                 | 8.7                   | 0.0  


Calculating job usage arbitrarily
=================================

flux-accounting also offers a way to report job usage different from displaying
a historical job usage value that factors in job decay. ``view-usage-report``
can generate a job usage report for users, banks, or associations that can be
filtered by start/end dates, how job usage is reported (e.g. by second,
minute, or hour) and/or how jobs are binned. Job usage reports are sent to
stdout upon completion and is a quick way to look at job usage on a system.

Examples
----------

By default, usage is grouped by association:

.. code-block:: console

    $ flux account view-usage-report
    association(nodesec)              total
    A:50001                          540.00
    A:50002                          420.00
    B:50003                          300.00
    TOTAL                           1260.00

But can also be grouped by user or bank:

.. code-block:: console

    $ flux account view-usage-report --report-type byuser
    user(nodesec)                     total
    50001                            540.00
    50002                            420.00
    50003                            300.00
    TOTAL                           1260.00

    $ flux account view-usage-report --report-type bybank
    bank(nodesec)                     total
    A                                960.00
    B                                300.00
    TOTAL                           1260.00

How usage is calculated can also be customized:

.. code-block:: console

    $ flux account view-usage-report --time-unit hour
    association(nodehour)             total
    A:50001                            0.15
    A:50002                            0.12
    B:50003                            0.08
    TOTAL                              0.35

Job size bins can also be created to group jobs by their sizes:

.. code-block:: console

    $ flux account view-usage-report --job-size-bins=1,2,3,4
    association(nodesec)                 1+             2+             3+             4+
    A:50001                          180.00         120.00           0.00         240.00
    TOTAL                            180.00         120.00           0.00         240.00
