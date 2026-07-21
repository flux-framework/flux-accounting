.. flux-help-section: flux account

=============================
flux-account-list-configs(1)
=============================


SYNOPSIS
========

**flux** **account** **list-configs** [OPTIONS]

DESCRIPTION
===========

.. program:: flux account list-configs

:program:`flux account list-configs` displays all key-value pairs stored in the
``config_table`` of the flux-accounting database.

OPTIONS
=======

.. option:: --fields

   Specify which fields to include in the output. Accepts a comma-separated
   list of field names (e.g., ``key,value``). By default, all fields are shown.

.. option:: --json

   Print the output in JSON format instead of a table.

.. option:: -o, --format

   Specify a custom output format using Python's string format syntax. Field
   names should be enclosed in curly braces (e.g., ``{key}->{value}``).

EXAMPLES
========

List all configuration parameters in table format:

.. code-block:: console

    $ flux account list-configs
    key                         | value
    ----------------------------+--------
    priority_usage_reset_period | 2419200
    priority_decay_half_life    | 604800
    decay_factor                | 0.5

List configurations in JSON format:

.. code-block:: console

    $ flux account list-configs --json
    [
      {"key": "priority_usage_reset_period", "value": "2419200"},
      {"key": "priority_decay_half_life", "value": "604800"},
      {"key": "decay_factor", "value": "0.5"}
    ]

List only the keys:

.. code-block:: console

    $ flux account list-configs --fields=key
    key
    ---------------------------
    decay_factor
    priority_decay_half_life
    priority_usage_reset_period

Use a custom format string:

.. code-block:: console

    $ flux account list-configs -o "{key}->{value}"
    key->value
    priority_usage_reset_period->2419200
    priority_decay_half_life->604800
    decay_factor->0.5

SEE ALSO
========

:man1:`flux-account-add-config`, :man1:`flux-account-edit-config`,
:man1:`flux-account-delete-config`, :man1:`flux-account-create-db`
