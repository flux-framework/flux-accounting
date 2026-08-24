=========================
flux-config-accounting(5)
=========================


DESCRIPTION
===========

The ``[accounting]`` TOML table configures the default values seeded into
the flux-accounting database when it is created with
:man1:`flux-account-create-db`. The path to a TOML file containing this
table is passed to :man1:`flux-account-create-db` with ``--config-path``.

The table is subdivided by function into sections: ``[accounting.usage]``
configures the job usage calculation, ``[accounting.priority]`` configures
the multi-factor priority plugin, and ``[accounting.queues]`` configures
queue policy.

Every key is optional; a key not present in the file keeps its built-in
default, and a database created without a configuration file is identical
to one created with a file containing only the default values shown below.

Durations may be expressed in `Flux Standard Duration (FSD)`_ (e.g. ``"7d"``)
or as a number of seconds, and must be positive and finite.

USAGE KEYS
==========

reset-period
   (optional) The amount of time before job usage gets reset to 0
   (default: ``"28d"``).

decay-half-life
   (optional) The contribution of historical usage in the amount of time
   on the composite job usage value (default: ``"7d"``).

decay-factor
   (optional) The amount of decay to apply to historical usage. Must be
   greater than 0.0 and less than 1.0 (default: ``0.5``).

weights
   (optional) A sub-table mapping each resource type to the weight it is
   given when calculating job usage: ``node`` (default: ``1.0``), ``core``
   (default: ``0.0``), and ``gpu`` (default: ``0.0``).

PRIORITY KEYS
=============

factors
   (optional) A sub-table mapping each priority factor used by the
   multi-factor priority plugin to its integer weight: ``fairshare``
   (default: ``100000``), ``queue`` (default: ``10000``), ``bank``
   (default: ``0``), and ``urgency`` (default: ``1000``).

QUEUES KEYS
===========

deny-unknown
   (optional) Reject jobs submitted to queues that are not defined in the
   flux-accounting database (default: ``false``).

EXAMPLE
=======

.. code-block:: toml

   [accounting.usage]
   reset-period = "28d"
   decay-half-life = "7d"
   decay-factor = 0.5

   [accounting.usage.weights]
   node = 1.0
   core = 0.0
   gpu = 0.0

   [accounting.priority.factors]
   fairshare = 100000
   queue = 10000
   bank = 0
   urgency = 1000

   [accounting.queues]
   deny-unknown = false

SEE ALSO
========

:man1:`flux-account-create-db`, :core:man5:`flux-config`

.. _Flux Standard Duration (FSD): https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_23.html
