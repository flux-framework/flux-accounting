.. flux-help-section: flux account

===========================
flux-account-add-config(1)
===========================


SYNOPSIS
========

**flux** **account** **add-config** KEY=VALUE

DESCRIPTION
===========

.. program:: flux account add-config

:program:`flux account add-config` adds a new key-value pair to the
``config_table`` in the flux-accounting database.

The command accepts a single key-value pair in the format ``KEY=VALUE``.

EXAMPLES
========

Add a custom configuration parameter:

.. code-block:: console

    $ flux account add-config my_custom_key=my_value

SEE ALSO
========

:man1:`flux-account-edit-config`, :man1:`flux-account-delete-config`,
:man1:`flux-account-create-db`
