.. _bank-info:

#######################################
Understanding The ``bank-info`` Command
#######################################

********
Overview
********

The ``bank-info`` command provides a comprehensive view of fairshare
and resource allocation information for banks and users within the
flux-accounting database. It displays normalized shares, usage
statistics, and fairshare values in a hierarchical tree structure that
reflects the organization of banks and their associations.

This command serves multiple purposes:

- **Quick status checks**: View current resource allocation and usage at a
  glance
- **Hierarchy visualization**: Understand the relationship between banks and
  users
- **Resource analysis**: Compare allocated shares versus actual usage

Unlike :man1:`flux-account-view-bank` and :man1:`flux-account-view-user`
which display detailed database attributes, ``bank-info`` focuses
specifically on share distribution and usage metrics that *may* affect job
scheduling priorities.

*****************
Command Execution
*****************

When called without options, ``bank-info`` displays information for the
current association. To view the entire database hierarchy, pass the ``-t``
flag along with the name of the root bank:

.. code-block:: console

    $ flux account bank-info -t root
    Name                     Shares  Norm Shares   Norm Usage   Level FS
    root                          1     1.000000     1.000000        inf
    A                             1     0.333333     0.000000         --
      user1                       1     0.166667     0.000000      0.500
      user2                       1     0.166667     0.000000      0.500
    B                             1     0.333333     0.000000         --
      user3                       1     0.333333     0.000000      0.500
    C                             1     0.333333     0.000000         --
      user1                       1     0.333333     0.000000      0.500

************************
Understanding the Output
************************

The output columns provide different perspectives on resource
allocation and usage:

In the example above, the normalized shares calculation proceeds as
follows:

- ``root`` has a normalized shares value of 1.0 (by definition, this represents
  a 100% share of all resources)
- Banks ``A``, ``B``, and ``C`` each have 1 share out of 3 total sibling
  shares, so each gets :math:`1/3 * 1.0 = 0.333333` normalized shares
- ``user1`` in bank ``A`` has 1 share out of 2 total shares in that
  bank, so they get :math:`1/2 * 0.333333 = 0.166667` normalized shares
- ``user3`` in bank ``B`` is the only user, so they get
  :math:`1/1 * 0.333333 = 0.33333` normalized shares

Name
  The bank or username, where the level of indentation represents hierarchical
  depth within the tree structure. Associations are indented one additional
  space beyond their parent bank.

Shares
  The raw share allocation assigned to this bank or user within its
  parent.

Normalized Shares
  Normalized shares represent each entity's fraction of total root
  resources by multiplying share proportions up the bank tree. The
  calculation propagates from parent to child:

  .. math::

    \text{S}_{normalized_{node}} = \frac{\text{shares}_{node}}{\text{shares}_{node+siblings}} \times \text{S}_{normalized_{parent}}

  The root bank always has normalized shares of 1.0. Each child's
  normalized shares are computed by taking its fraction of siblings'
  shares and multiplying by its parent's normalized shares. This
  multiplicative calculation ensures that normalized shares always sum
  to the parent's normalized shares and represent the entity's portion
  of the root allocation.

Usage
  Total job usage accumulated by this entity (displayed only with
  ``--verbose``). For associations, this is their individual usage.
  For banks, this is the sum of all usage by users within that bank.

Norm Usage
  Normalized usage represents this entity's proportion of total system
  usage. Calculated as:

  .. math::

    \text{Usage}_{normalized_{node}} = \frac{\text{Usage}_{node}}{\text{Usage}_{root}}

Level FS
  The fair-share value for the association. For more details on
  fairshare calculation, see :doc:`fair-share`.

********
Examples
********

Monitoring resource consumption
===============================

We can compare allocated shares against actual usage to identify
over-consuming or under-utilizing associations:

.. code-block:: console

    $ flux account bank-info -t root -v
    Name                      Shares  Norm Shares        Usage   Norm Usage  Level FS
    root                           1     1.000000      10000.0     1.000000       inf
     A                             7     0.700000       8500.0     0.850000        --
      user1                        3     0.300000       5000.0     0.500000     0.333
      user2                        4     0.400000       3500.0     0.350000     0.667
     B                             3     0.300000       1500.0     0.150000        --
      user3                        1     0.300000       1500.0     0.150000     1.000

In this example, bank ``A`` has 7 shares out of 10 total, giving it 70% of root
resources (0.7 normalized shares), and users within it are responsible for 85%
of the system's total usage. 

Within bank ``A``, ``user1`` has 3 shares out of 7, so it has
:math:`3/7 \times 0.7 = 0.3` (30% of root resources) normalized shares, and is
responsible for 50% of the system's total usage. Similarly, ``user2`` gets
:math:`4/7 * 0.7 = 0.4` (40% of root resources) normalized shares.

Bank ``B`` has 3 shares out of 10 total, giving it 0.3 normalized shares, and
its sole user ``user3`` is responsible for 15% of the system's total usage.

Analyzing hierarchical share distribution
=========================================

Shares cascade through multiple levels of banks all the way down to users:

.. code-block:: console

    $ flux account bank-info -t root
    Name                      Shares  Norm Shares   Norm Usage  Level FS
    root                           1     1.000000     0.000000       inf
     A                           100     0.500000     0.000000        --
      Aa                          60     0.300000     0.000000        --
       user1                       1     0.100000     0.000000     0.500
       user2                       2     0.200000     0.000000     0.500
      Ab                          40     0.200000     0.000000        --
       user3                       1     0.200000     0.000000     0.500
     B                           100     0.500000     0.000000        --
      user4                        1     0.500000     0.000000     0.500

This multi-level hierarchy demonstrates how normalized shares propagate down
the tree:

- Banks ``A`` and ``B`` each have 100 shares out of 200 total, so they each
  get: :math:`100/200 * 1.0 = 0.5` normalized shares
- Bank ``Aa`` has 60 shares out of 100 within ``A``, so it gets:
  :math:`60/100 * 0.5 = 0.3` normalized shares
- Bank ``Ab`` has 40 shares out of 100 within ``A``, so it gets:
  :math:`40/100 * 0.5 = 0.2` normalized shares
- ``user1`` has 1 share out of 3 total user shares in ``Aa``, so they get:
  :math:`1/3 * 0.3 = 0.1` normalized shares
- ``user2`` has 2 shares out of 3 total user shares in ``Aa``, so they get:
  :math:`2/3 * 0.3 = 0.2` normalized shares
- ``user3`` is the only user in ``Ab``, so they get: :math:`1/1 * 0.2 = 0.2`
  normalized shares
- ``user4`` is the only user in ``B``, so they get: :math:`1/1 * 0.5 = 0.5`
  normalized shares

Each entity's normalized shares represent its fraction of total root
resources.

****************
Related Commands
****************

- :man1:`flux-account-view-bank` - Display detailed database attributes for a bank
- :man1:`flux-account-view-user` - Display detailed database attributes for a user
- :man1:`flux-account-add-bank` - Add a new bank to the hierarchy
- :man1:`flux-account-add-user` - Add a user association to a bank
- :man1:`flux-account-edit-bank` - Modify bank attributes including shares
- :man1:`flux-account-edit-user` - Modify user association attributes including shares

********
See Also
********

:doc:`fair-share`, :doc:`job-priorities`, :doc:`database-administration`
