=========================
flux-config-accounting(5)
=========================


DESCRIPTION
===========

accounting.factor-weights
-------------------------

The flux-accounting priority plugin can be configured to assign different
weights to the different factors used when calculating a job's priority.
Assigning a higher weight to a factor will result in it having more
influence in the calculated priority for a job. By default, the factors in
the priority plugin have the following weights:

+-------------+--------+
| factor      | weight |
+=============+========+
| fairshare   | 100000 |
+-------------+--------+
| queue       | 10000  |
+-------------+--------+

The ``accounting.factor-weights`` sub-table may contain the following keys:


KEYS
^^^^

fairshare
    Integer value that represents the weight to be associated with an
    association's fairshare value.

queue
   Integer value that represents the weight associated with submitting a job
   to a certain queue.


EXAMPLE
^^^^^^^

::

   [accounting.factor-weights]
   fairshare = 10000
   queue = 1000

accounting.queue-priorities
---------------------------

The priority plugin's queues can also be configured to have a different
associated integer priority in the TOML file. Queues can positively or
negatively affect a job's calculated priority depending on the priority
assigned to each one. By default, queues have an associated priority of 0,
meaning they do not affect a job's priority at all.

If a queue defined in the config file is unknown to the priority plugin, it
will add the queue to its internal map. Otherwise, it will update the queue's
priority with the new value.

The ``accounting.queue-priorities`` sub-table should list any configured queue
as the key and its associated integer priority as the value.

EXAMPLE
^^^^^^^

::

   [accounting.queue-priorities]
   bronze=100
   silver=200
   gold=300
