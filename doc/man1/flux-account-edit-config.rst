.. flux-help-section: flux account

============================
flux-account-edit-config(1)
============================


SYNOPSIS
========

**flux** **account** **edit-config** KEY1=VALUE1 [KEY2=VALUE2 ...]

DESCRIPTION
===========

.. program:: flux account edit-config

:program:`flux account edit-config` modifies one or more configuration
parameters in the flux-accounting database's ``config_table``. This command
allows administrators to change certain database settings, such as job usage
calculation parameters.

The command accepts one or more key-value pairs in the format ``KEY=VALUE``,
separated by spaces.

SEE ALSO
========

:man1:`flux-account-create-db`, :man1:`flux-account-add-config`,
:man1:`flux-account-delete-config`
