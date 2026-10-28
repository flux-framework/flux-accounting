.. _job-usage-calculation:

#####################
Job Usage Calculation
#####################

By default, the raw job usage factor for an association is defined as the sum
of products of number of nodes used (``nnodes``) and time elapsed
(``t_elapsed``). To calculate the raw usage for a given association *U*:

:math:`U = sum(nnodes \times t\_elapsed)`

flux-accounting keeps track of job usage in a table according to two properties
that are set when the database is first created: **PriorityDecayHalfLife** and
**PriorityUsageResetPeriod**. Each of these parameters represent a duration by
which to hold usage factors up to the time period where jobs no longer play a
factor in calculating a usage factor. If these options aren't specified, the
table defaults to 4 usage columns, each which represent one week's worth of
jobs.

In periodic mode, the **job_usage_per_association** table stores past job
usage factors per association. When an association is first added to the
**association** table, it is also added to the
**job_usage_per_association** table.

The value of **PriorityDecayHalfLife** determines the amount of time that
represents one "usage period" of jobs. flux-accounting filters out its ``jobs``
table and retrieves an association's jobs that have completed in the usage
period.

As time goes on and usage periods get older, their raw usage value has a decay
factor :math:`D` (by default, 0.5) applied to them before they are added to the
user's current raw usage factor.

:math:`U_{past} = (D \times U_{last\_period}) + (D \times D \times U_{period-2}) + ...`

After the current usage factor is calculated, it is written to the first usage
bin in the **job_usage_per_association** table along with the other, older
factors. The oldest factor then gets removed from the table since it is no
longer needed.

Continuous decay mode
=====================

By default, flux-accounting uses the periodic bin calculation described above.
Administrators may opt in to elapsed-time decay with
``decay_method=continuous``. Continuous mode still charges only
completed jobs already recorded in the ``jobs`` table, but it decays the
existing scalar usage value on each update instead of rotating discrete bins:

:math:`U_{new} = (U_{old} \times D^{\Delta t / H}) + U_{current}`

Here, :math:`D` is ``decay_factor``, :math:`H` is
``priority_decay_half_life``, and :math:`\Delta t` is the elapsed time since
the previous continuous usage update. With the default values, half of a
contribution remains after one week.

In continuous mode, ``association_table.job_usage`` stores the complete
continuously decayed usage value. ``job_usage_per_association_table`` remains
periodic-mode storage only, so detailed bin breakdowns are unavailable while
continuous mode is active.

Newly completed jobs are decayed from their own ``t_inactive`` timestamp to
the current update time before they are added to the scalar usage value.

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

In periodic mode, an association's historical job usage is the value reported
in the ``job_usage`` column, and it may be made up of multiple usage factors.
The ``view-user`` command offers a ``-J/--job-usage`` optional argument, which
will return all of the association's job usage columns that make up its
historical job usage value. In continuous mode, this detailed bin breakdown is
unavailable because all usage is stored in just one value: the ``job_usage``
column in ``association_table``.

.. code-block:: console

    $ flux account view-user --parsable -J moussa
    username | userid | bank     | usage_factor_period_0 | usage_factor_period_1 | usage_factor_period_2 | usage_factor_period_3
    ---------+--------+----------+-----------------------+-----------------------+-----------------------+----------------------
    moussa   | 12345  | A        | 100.0                 | 243.5                 | 8.7                   | 0.0  


Resetting the usage for a bank
==============================

The job usage value for a bank (and all of the users under that bank) can be
reset with the :man1:`flux-account-clear-usage` command. This will allow you to
quickly clear any amount of recently accrued usage, which, on a high-traffic
system, can ultimately bump up its users' fair-share values after the entire
hierarchy's job usage and fair-share values are updated.

An optional timestamp can also be specified when running this command to tell
flux-accounting to *only* consider jobs newer than said timestamp with the
``--ignore-older-than`` optional argument. By default, the ``clear-usage``
command will notify any future job usage updates to ignore jobs submitted under
that bank older than when the command was issued.

Reconfiguring Job Usage Parameters After Deployment
===================================================

As system workloads and scheduling policies evolve, administrators may need to
adjust how job usage is tracked and weighted. For example, a system
transitioning from long-running batch jobs to shorter, interactive workloads
may benefit from shorter usage periods and more frequent bin rotations.
Similarly, administrators may want to tune the decay factor to give more or
less weight to historical usage when calculating fair-share values. These
adjustments can help ensure that job usage calculations remain aligned with the
current usage patterns and scheduling priorities of the system.

The job usage calculation parameters (``priority_decay_half_life``,
``priority_usage_reset_period``, and ``decay_factor``) can be changed after the
database has been deployed using the :man1:`flux-account-edit-config` command.
This allows administrators to adjust how job usage is tracked and decayed
without recreating the database.

Using the ``edit-config`` command
---------------------------------

The ``edit-config`` command accepts one or more key-value pairs to update in
the configuration table. The following configuration keys control job usage
calculation:

- ``decay_method``: Selects ``periodic`` (the default) or
  ``continuous`` usage decay.

- ``priority_decay_half_life``: The time period representing one "usage period"
  of jobs. This determines how often usage bins are rotated in periodic mode,
  and the elapsed-time half-life in continuous mode.

- ``priority_usage_reset_period``: The total time span over which historical
  job usage is tracked. This determines the total number of usage bins in
  periodic mode, and is not used by continuous mode.

- ``decay_factor``: The multiplier applied to older usage periods when
  calculating historical usage. In continuous mode, it is applied
  proportionally over elapsed time. The default value is 0.5.

Values for ``priority_decay_half_life`` and ``priority_usage_reset_period`` can
be specified using `Flux Standard Duration (FSD)`_ format or in seconds. FSD
supports units such as ``m`` (minutes), ``h`` (hours), and ``d`` (days).

The Reconfiguration Process
----------------------------

When you modify ``priority_decay_half_life``,
``priority_usage_reset_period``, or ``decay_factor`` in periodic mode, the
``edit-config`` command will:

1. Calculate the new number of usage bins based on the updated parameters
2. Delete all existing usage bin data for every association
3. Re-create the correct number of usage bins for each association (in periodic
   mode)
4. Reset all associations' job history timestamps so that the next usage update
   recalculates usage from scratch with the new configuration

Because existing bin contents are removed and older jobs are excluded,
periodic reconfiguration effectively resets usage to ``0.0``.

.. note::

    Reconfiguring the above parameters does **not** clear job records from the
    flux-accounting database. These records can still be viewed with ``flux
    account view-job-records``.

Switching from periodic mode to continuous mode preserves each association's
current historical ``job_usage`` value, clears periodic usage-bin rows, and
starts the continuous decay clock at the time of the config change. Switching
from continuous mode back to periodic mode recreates periodic bins and resets
association and bank usage to ``0.0`` because the continuous scalar value
cannot be reconstructed into discrete historical bins.

In continuous mode, changing ``priority_decay_half_life`` or
``decay_factor`` resets association and bank usage to ``0.0`` and starts a new
continuous decay clock. Changing ``priority_usage_reset_period`` in continuous
mode only takes effect after switching back to periodic mode.

When ``decay_method`` is changed in the same ``edit-config`` command as
``priority_decay_half_life`` or ``decay_factor``, the mode switch determines
what happens to usage. For example, switching from periodic to continuous
while also changing ``priority_decay_half_life`` still preserves each
association's current ``job_usage`` value, and the new half-life is applied to
that value from the next usage update onward.

You can also view the current configuration values at any time:

.. code-block:: console

    $ flux account list-configs
    key                         | value
    ----------------------------+--------
    priority_usage_reset_period | 2419200
    priority_decay_half_life    | 604800
    decay_factor                | 0.5
    decay_method                | periodic

Important Considerations
------------------------

.. warning::

    Reconfiguring periodic-mode usage parameters, changing continuous-mode
    decay parameters, or switching from continuous mode back to periodic mode,
    resets all job usage values to 0.0 for every association in the database.
    This has several important implications:

    - **fair-share values will be affected**: Since fair-share calculations
      depend on job usage, all fair-share values will also see changes based on
      the new usage data.

    - **periodic usage bins are rebuilt**: In periodic mode, the system will
      reconstruct usage bins from scratch for *every* association using the new
      configuration. Depending on the size of your ``association_table``, this
      may take some time during the reconfiguration.

    - **historical usage is no longer considered**: flux-accounting will **no
      longer** consider past jobs towards an association's job usage value;
      every association's and bank's job usage will be reset to 0.0.

    - **timing matters**: Since flux-accounting will be re-calculating job
      usage bins per-association, many rows in the database will be affected.
      Consider performing reconfigurations during maintenance windows or
      periods of low activity to other concurrent operations on the database.

    - **changes cannot be undone**: Once the reconfiguration is confirmed and
      committed, you cannot restore the previous usage values. Plan your
      configuration changes carefully.

The number of usage bins :math:`N` created for each association is calculated
as:

:math:`N = priority\_usage\_reset\_period / priority\_decay\_half\_life`

For example, with the default values of a 4-week reset period and 1-week
half-life, each association has 4 usage bins. Changing to an 8-hour half-life
and 24-hour reset period would result in 3 usage bins per association.

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

But can also be grouped by user, bank, or job name. When grouping by job name,
jobs whose name cannot be determined are reported under ``(unknown)``:

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

    $ flux account view-usage-report --report-type byjobname
    jobname(nodesec)                  total
    shared                           480.00
    /path/trailing/                  240.00
    pipeline                         240.00
    fallback                         120.00
    named with space                 120.00
    (unknown)                         60.00
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

Configuring Resource Weights
=============================

The raw job usage formula can be configured to weight different
resource types. By default, usage is calculated as
:math:`sum(nnodes \times t\_elapsed)`, but flux-accounting supports
configurable weights for nodes, cores, and GPUs:

:math:`U = sum((nnodes \times w_{node} + ncores \times w_{core} +`
:math:`ngpus \times w_{gpu}) \times t\_elapsed)`

Three configuration keys control these weights:

* ``node_weight`` (default: 1.0)
* ``core_weight`` (default: 0.0)
* ``gpu_weight`` (default: 0.0)

Each of the resource weights can be changed and viewed with the ``edit-config``
and ``view-config`` commands, respectively.

.. warning::

    Consider clearing all current job usage from banks and associations
    *before* changing the weights for resource types to ensure consistency with
    how job usage (and subsequently, fair-share) is calculated throughout the
    database hierarchy.

Example Usage Calculations
---------------------------

Consider a job using 1 node, 8 cores, 2 GPUs for 100 seconds. Using
flux-accounting's default resource weights, the usage for this job
becomes:

:math:`U = (1 \times 1.0 + 8 \times 0.0 + 2 \times 0.0) \times 100 = 100.0`

If we were to add weights for core usage, the usage now becomes:

:math:`U = (1 \times 1.0 + 8 \times 1.0 + 2 \times 0.0) \times 100 = 900.0`

or adding significant more weight to GPU usage, the usage now is calculated as:

:math:`U = (1 \times 1.0 + 8 \times 0.0 + 2 \times 10.0) \times 100 = 2100.0`

Configuring resources to have different weights can be useful for certain kinds
of cost-based accounting depending on how your system is built and how you want
to consider usage of your system.

.. _Flux Standard Duration (FSD): https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_23.html
