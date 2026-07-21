.. flux-help-section: flux account

==============================
flux-account-delete-config(1)
==============================


SYNOPSIS
========

**flux** **account** **delete-config** KEY

DESCRIPTION
===========

.. program:: flux account delete-config

:program:`flux account delete-config` removes a key-value pair from the
``config_table`` in the flux-accounting database.

The command accepts a single key to delete.

PROTECTED KEYS
==============

The following keys are protected and cannot be deleted as they are essential
for job usage calculation:

- ``priority_usage_reset_period``
- ``priority_decay_half_life``
- ``decay_factor``

Attempting to delete any of these keys will result in an error.

SEE ALSO
========

:man1:`flux-account-add-config`, :man1:`flux-account-edit-config`,
:man1:`flux-account-create-db`
