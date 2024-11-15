.. _fair-share:

######################
Fair-Share Calculation
######################

*key terms: weighted walk*

This document outlines how fair-share is calculated for a hierarchy of banks
and users in a flux-accounting database.

********
Overview
********

Fair-share is a metric used to ensure equitable resource allocation among
associations within a shared system. It represents the ratio between the amount
of resources an association is allocated versus the amount actually consumed.

The fair-share value influences an association's priority when submitting jobs
to the system, adjusting dynamically to reflect current usage compared to
allocated shares. High consumption relative to allocation can decrease an
association's fair-share value, reducing their priority for future resource
allocation, thereby promoting balanced usage across all associations to
maintain system fairness and efficiency.

Fair-share values range between 0 and 1, with values closer to 1 indicating
low prior usage relative to allocated resources. Associations are granted an
initial fair-share value of 0.5 when they are first added to the
flux-accounting database.

flux-accounting dynamically adjusts fair-share as resources are consumed.
Historical job usage diminishes in signficance over time, ensuring that
short-term heavy usage does not permanently impact an association's fair-share.

***********************
Weighted Tree Structure
***********************

The hierarchy of banks and users in the flux-accounting database can be
described in a hierarchical weighted tree structure. Below is an example
structure:

.. code-block:: text

    root
    ├── A
    │   ├── user1
    │   └── user2
    ├── B
    │   ├── user3
    │   └── user4
    └── C
        ├── user2
        └── user5

This structure is used to model relationships between banks and users, where:

- each bank and user can have associated usage and shares
- parent banks aggregate information about their subtree
- job usage and allocated shares are used to calculate the fair-share for each bank and user

Each bank in the hierarchy can have a parent (aside from the root bank) and
children, forming a tree. The sub-banks which users belong can be considered
intermediate nodes, and users are the leaf nodes.

The node's attributes help determine its position and contribution within the
tree. These attributes consist of:

- **shares**: the node's share in its parent node
- **usage**: how many resources the node has consumed

The ``weighted_tree_node_t`` class models a node in a weighted hierarchical
tree used to calculate fair-share distribution across a resource hierarchy (in
flux-accounting's case, a hierarchy of banks and users).

***************
The Calculation
***************

The fair-share calculation can be described as:

.. math::

  \text{F} = \frac{\text{rank}_{node}}{\text{N}_{siblings}}

where the rank of a node :math:`n` is determined by comparing its weight to
that of its siblings. Weights (and thus, ranks) are sorted in descending order,
first by bank, and then by user.

.. math::

  \text{weight}_{n} = \frac{\text{shares}_{weighted}}{\text{usage}_{weighted}}

The weighted shares and weighted usage values are calculated by looking at the
proportion of a node's shares and usage compared to its siblings:

.. math::

  \text{shares}_{weighted} = \frac{\text{shares}_{n}}{\text{shares}_{n+siblings}}

.. math::

  \text{usage}_{weighted} = \frac{\text{usage}_{n}}{\text{usage}_{n+siblings}}

The banks are then sorted in descending order by weight. Once the banks are
sorted, the users in each bank are then sorted by their respective weights.

an example
----------

Consider the following hierarchy of accounts and users, represented in a table format:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10 10

   * - parent
     - name
     - shares
     - usage
   * - root
     -
     - 1000
     - 133
   * - root
     - account1
     - 1000
     - 121
   * - account1
     - leaf.1.1
     - 10000
     - 100
   * - account1
     - leaf.1.2
     - 1000
     - 11
   * - account1
     - leaf.1.3
     - 100000
     - 10
   * - root
     - account2
     - 100
     - 11
   * - account2
     - leaf.2.1
     - 100000
     - 8
   * - account2
     - leaf.2.2
     - 10000
     - 3
   * - root
     - account3
     - 10
     - 1
   * - account3
     - leaf.3.1
     - 100
     - 0
   * - account3
     - leaf.3.2
     - 10
     - 1

The tree hierarchy is as follows:

.. code-block:: text

   root
   ├── account1
   │   ├── leaf.1.1
   │   ├── leaf.1.2
   │   └── leaf.1.3
   ├── account2
   │   ├── leaf.2.1
   │   └── leaf.2.2
   └── account3
       ├── leaf.3.1
       └── leaf.3.2

Let's walk through the weight calculation for one of the users in this
hierarchy: ``leaf.3.2``:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10 10

   * - parent
     - name
     - shares
     - usage
   * - account3
     - leaf.3.2
     - 10
     - 1

We can calculate ``leaf.3.2``'s weighted shares with the equation we defined
above:

.. math::

  \text{s_weighted}_{leaf.3.2} = \frac{\text{shares}_{leaf.3.2}}{\text{shares}_{leaf.3.2+siblings}} = \frac{\text{10}}{\text{110}} = \text{0.0909091}

.. math::

  \text{u_weighted}_{leaf.3.2} = \frac{\text{usage}_{leaf.3.2}}{\text{usage}_{leaf.3.2+siblings}} = \frac{\text{1}}{\text{1}} = \text{1}

So, the final weight for ``leaf.3.2`` can be calculated as the following:

.. math::

  \text{weight}_{leaf.3.2} = \frac{\text{s_weighted}_{leaf.3.2}}{\text{u_weighted}_{leaf.3.2}} = \frac{\text{0.0909091}}{\text{1}} = \text{0.0909091}

We apply the same process to a bank that holds users. Take ``account3`` for example:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10 10

   * - parent
     - name
     - shares
     - usage
   * - root
     - account3
     - 10
     - 1

.. math::

  \text{s_weighted}_{account3} = \frac{\text{shares}_{account3}}{\text{shares}_{account3+siblings}} = \frac{\text{10}}{\text{1110}} = \text{0.0909091}

.. math::

  \text{u_weighted}_{account3} = \frac{\text{usage}_{account3}}{\text{usage}_{account3+siblings}} = \frac{\text{1}}{\text{133}} = \text{0.0075188}

.. math::

  \text{weight}_{account3} = \frac{\text{s_weighted}_{account3}}{\text{u_weighted}_{account3}} = \frac{\text{0.00900901}}{\text{0.0075188}} = \text{1.1982}

We repeat this process for every user and sub-bank in the hierarchy:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10

   * - parent
     - name
     - weight
   * - root
     -
     -
   * - root
     - account1
     - 0.990246
   * - account1
     - leaf.1.1
     - 0.109009
   * - account1
     - leaf.1.2
     - 0.0990991
   * - account1
     - leaf.1.3
     - 10.9009
   * - root
     - account2
     - 1.08927
   * - account2
     - leaf.2.1
     - 1.25
   * - account2
     - leaf.2.2
     - 0.333333
   * - root
     - account3
     - 1.1982
   * - account3
     - leaf.3.1
     - 1.84467
   * - account3
     - leaf.3.2
     - 0.909091

After sorting the banks in descending order, we see that ``account3`` has the
highest weight at 1.1982, followed by ``account2`` at 1.08927, and then finally
``account1`` at 0.990246. Each bank's set of users are then sorted by their
weight. If we look at ``account3``, we see that ``leaf.3.1`` has the highest
weight at 1.84467. Therefore, ``leaf.3.1`` receives the highest rank of all of
the users. ``leaf.3.2`` follows with the second highest rank, and ``account3``
is now fully sorted. We repeat this process for the rest of the banks in the
hierarchy:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10 10

   * - rank
     - parent
     - name
     - weight
   * -
     -
     - root
     -
   * -
     - root
     - account3
     - 1.1982
   * - **1**
     - account3
     - leaf.3.1
     - 1.84467
   * - **2**
     - account3
     - leaf.3.2
     - 0.909091
   * -
     - root
     - account2
     - 1.08927
   * - **3**
     - account2
     - leaf.2.1
     - 1.25
   * - **4**
     - account2
     - leaf.2.2
     - 0.333333
   * -
     - root
     - account1
     - 0.990246
   * - **5**
     - account1
     - leaf.1.3
     - 10.9009
   * - **6**
     - account1
     - leaf.1.1
     - 0.109009
   * - **7**
     - account1
     - leaf.1.2
     - 0.0990991

To calculate the fair-share value :math:`F` for each user, we simply divide
each user's rank by the number of users. As an example, take ``leaf.2.2``,
which ranks 4th among all of the users:

.. math::

  \text{F}_{leaf.2.2} = \frac{\text{rank}_{leaf.2.2}}{\text{N}_{users}} = \frac{\text{4}}{\text{7}} = \text{0.571429}

After performing a *weighted walk* on this hierarchy, the fair-share distribution
for the users look like this:

.. list-table::
   :header-rows: 1
   :widths: 10 15 10 10 10

   * - bank
     - username
     - raw shares
     - raw usage
     - fair-share
   * - root
     -
     - 1000
     - 133.0
     -
   * - account1
     -
     - 1000
     - 121.0
     -
   * - account1
     - leaf.1.1
     - 10000
     - 100.0
     - 0.285714
   * - account1
     - leaf.1.2
     - 1000
     - 11.0
     - 0.142857
   * - account1
     - leaf.1.3
     - 100000
     - 10.0
     - 0.428571
   * - account2
     -
     - 100
     - 11.0
     -
   * - account2
     - leaf.2.1
     - 100000
     - 8.0
     - 0.714286
   * - account2
     - leaf.2.2
     - 10000
     - 3.0
     - 0.571429
   * - account3
     -
     - 10
     - 1.0
     -
   * - account3
     - leaf.3.1
     - 100
     - 0.0
     - 1.0
   * - account3
     - leaf.3.2
     - 10
     - 1.0
     - 0.857143

********
Glossary
********

weighted walk
  The traversal of a hierarchy starting from the root, during which the weights
  for each bank and user are calculated.
