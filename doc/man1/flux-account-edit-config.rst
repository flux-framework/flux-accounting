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

The ``decay_method`` key selects how historical job usage is decayed.
The default value is ``periodic``. Setting it to ``continuous`` preserves the
current historical job usage value for each association and applies
elapsed-time decay on future usage updates. Detailed usage-bin breakdowns are
unavailable while continuous mode is active. Setting it back to ``periodic``
recreates periodic usage bins and resets association and bank usage to ``0.0``.
Changing ``priority_usage_reset_period``, ``priority_decay_half_life``, or
``decay_factor`` recreates periodic usage bins and resets usage to ``0.0``
in periodic mode. In continuous mode, changing ``priority_decay_half_life``
or ``decay_factor`` resets association and bank usage to ``0.0``.
When ``decay_method`` is changed in the same command as these keys, the mode
switch determines what happens to usage: switching to ``continuous`` preserves
usage, and switching to ``periodic`` resets it.

SEE ALSO
========

:man1:`flux-account-create-db`, :man1:`flux-account-add-config`,
:man1:`flux-account-delete-config`
