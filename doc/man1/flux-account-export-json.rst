.. flux-help-section: flux account

===========================
flux-account-export-json(1)
===========================


SYNOPSIS
========

**flux** **account** **export-json**

DESCRIPTION
===========

.. program:: flux account export-json

:program:`flux account export-json` will output certain flux-accounting tables
as a JSON object. The intention of this command is to extract the tables
required by the multi-factor priority plugin into a JSON object to be loaded
*with* the plugin during ``flux jobtap load``.

EXAMPLES
--------

The output of the ``export-json`` command can be passed to the load of the
multi-factor priority plugin.

.. code-block:: console

 $ flux jobtap load path/to/mf_priority.so "config=$(flux account export-json)"
