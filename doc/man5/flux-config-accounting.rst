=========================
flux-config-accounting(5)
=========================


DESCRIPTION
===========

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
====

fairshare
    Integer value that represents the weight to be associated with an
    association's fairshare value.

queue
   Integer value that represents the weight associated with submitting a job
   to a certain queue.


EXAMPLE
=======

::

   [accounting.factor-weights]
   fairshare = 10000
   queue = 1000
