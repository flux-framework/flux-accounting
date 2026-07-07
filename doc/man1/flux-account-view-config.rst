.. flux-help-section: flux account

============================
flux-account-view-config(1)
============================


SYNOPSIS
========

**flux** **account** **view-config** KEY [OPTIONS]

DESCRIPTION
===========

.. program:: flux account view-config

:program:`flux account view-config` displays a specific key-value pair from the
``config_table`` in the flux-accounting database.

The command accepts a single key and displays its corresponding value.

OPTIONS
=======

.. option:: --json

   Print the output in JSON format instead of a table.

.. option:: -o, --format

   Specify a custom output format using Python's string format syntax. Field
   names should be enclosed in curly braces (e.g., ``{key}: {value}``).

EXAMPLES
========

View a configuration parameter in table format:

.. code-block:: console

    $ flux account view-config decay_factor
    key          | value
    -------------+------
    decay_factor | 0.5

View a configuration parameter in JSON format:

.. code-block:: console

    $ flux account view-config decay_factor --json
    {"key": "decay_factor", "value": "0.5"}

Use a custom format string:

.. code-block:: console

    $ flux account view-config decay_factor -o "{key}->{value}"
    key->value
    decay_factor->0.5

SEE ALSO
========

:man1:`flux-account-list-configs`, :man1:`flux-account-add-config`,
:man1:`flux-account-edit-config`, :man1:`flux-account-delete-config`
