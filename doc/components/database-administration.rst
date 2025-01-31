.. _database-administration:

#######################################
Flux Accounting Database Administration
#######################################

This document outlines the various methods of administration on the
flux-accounting database.

********
Overview
********

The tables in the flux-accounting database stores information for associations,
banks, job records, queues, and projects.

For associations, shares, limits, queue and project permissions, and bank
membership can be managed.

**********************************
Interacting With the Accounting DB
**********************************

In order to add, edit, or remove information from the flux-accounting database,
you must also have read/write access to the directory that the DB file resides
in. The `SQLite documentation <https://sqlite.org/omitted.html>`_ states:

    Since SQLite reads and writes an ordinary disk file, the only access
    permissions that can be applied are the normal file access permissions of
    the underlying operating system.

flux-accounting provides an interface to the SQLite database containing all of
the aforementioned data for associations, banks, queues, and projects. Commands
can be run to add/remove all of these, edit certain attributes, and view this
information in different formats. See ``flux account --help`` to list all of
the available flux-accounting commands.

The bank/association database hierarchy assumes a tree structure, meaning that
there is one root bank which all other banks and associations descend from:

.. code-block:: console

 $ flux account view-bank root -t

 Account                         Username           RawShares            RawUsage           Fairshare
 root                                                       1                 0.0
  bank_A                                                    1                 0.0
   bank_A                          user_1                   1                 0.0                 0.5
  bank_B                                                    1                 0.0
   bank_B                          user_2                   1                 0.0                 0.5
   bank_B                          user_3                   1                 0.0                 0.5
  bank_C                                                    1                 0.0
   bank_C_a                                                 1                 0.0
    bank_C_a                       user_4                   1                 0.0                 0.5
   bank_C_b                                                 1                 0.0
    bank_C_b                       user_5                   1                 0.0                 0.5
    bank_C_b                       user_6                   1                 0.0                 0.5

Multiple levels of banks can be defined under this root bank. Users can belong
to more than one bank and will have at most one default bank.

To add a bank to the database, you can use the ``flux account add-bank``
command. Each ``add-bank`` call requires a bank name, their allocated shares,
and a parent bank name (if it is not the root bank):

.. code-block:: console

 $ flux account add-bank root 1
 $ flux account add-bank --parent-bank=root bank_A 1

From here, users can be added to these banks to create *associations*, a
2-tuple combination of a username and bank name:

.. code-block:: console

 $ flux account add-user --username=user_1 --bank=bank_A

If you wish to delete an association or bank from the database, you can run the
``flux account delete-user`` or ``flux account delete-bank`` commands. Note
that this will not actually remove the association's or bank's row from the
table where their data is stored, but will instead set their ``active`` column
to 0. To re-enable an association's ``active`` status, simply re-add them with
``flux account add-user``. To permanently remove an association or a bank, pass
the ``--force`` option to ``delete-user``.

.. warning::
    Permanently deleting rows from the ``association_table`` or ``bank_table``
    can affect the fair-share calculation for other rows in their respective
    tables. Proceed with caution when deleting rows with ``--force``.

Information for associations can be viewed in more than one format and
customized:

.. code-block:: console

 $ flux account view-user user_1
 
 [
   {
     "creation_time": 1738269371,
     "mod_time": 1738269371,
       "active": 1,
       "username": "user_1",
       "userid": 5001,
       "bank": "bank_A",
       "default_bank": "bank_A",
       "shares": 1,
       "job_usage": 0.0,
       "fairshare": 0.5,
       "max_running_jobs": 5,
       "max_active_jobs": 7,
       "max_nodes": 2147483647,
       "max_cores": 2147483647,
       "queues": "",
       "projects": "*",
       "default_project": "*"
   }
 ]

 $ flux account view-user user_1 --parsable --fields=username,userid,bank

 username | userid | bank   | fairshare
 ---------+--------+--------+----------
 user_1   | 5001   | bank_A | 0.5

If you are familiar with SQLite syntax, you can also launch into an interactive
SQLite shell. From there, you can open the database file and interface with
any of the tables using SQLite commands:

.. code-block:: console

 $ sqlite3 path/to/FluxAccounting.db
 SQLite version 3.24.0 2018-06-04 14:10:15
 Enter ".help" for usage hints.
 Connected to a transient in-memory database.
 Use ".open FILENAME" to reopen on a persistent database.

 sqlite>

To get nicely formatted output from queries (like headers for the tables and
proper spacing), you can also set the following options in your shell:

.. code-block:: console

 sqlite> .mode columns
 sqlite> .headers on

This will output queries like the following:

.. code-block:: console
 
 sqlite> SELECT * FROM association_table;
 creation_time  mod_time    deleted     username    bank        shares      max_jobs    max_wall_pj
 -------------  ----------  ----------  ----------  ----------  ----------  ----------  -----------
 1605309320     1605309320  0           fluxuser    foo         1           1           60       


**********************************
Flux-Accounting Data Import/Export
**********************************

Multiple rows of data can be loaded to the database at once using ``.csv`` files
and the ``flux account pop-db`` command. Run ``flux account pop-db --help`` for
``.csv`` formatting instructions.

User and bank information can also be exported from the database using the
``flux account export-db`` command, which will extract information from both the
user and bank tables and place them into ``.csv`` files.
