.. _projects:

########
Projects
########

Projects in flux-accounting are another way for an association to be able to
charge their jobs against something *other than banks*. This allows
associations from different banks to all belong to the same project without
having to create a new bank.

If an association is added to the DB without specifying any projects, a default
project ``*`` is added for the association automatically, and jobs submitted
without specifying a project will fall under ``*``.

Every association who is added to the DB belongs to the ``*`` project
(regardless if other projects were specified when the association was added),
but will only run jobs under ``*`` if they do not already have another default
project.

If an association is added to the DB with a specified project name, any job
submitted without specifying a project name will fall under that project name.

********************
Configuring Projects
********************

Projects can be configured by adding them to the flux-accounting database with
``add-project``:

.. code-block:: console

    $ flux account add-project bronze
    $ flux account add-project silver
    $ flux account add-project gold

Projects, along with their total job usage, can be listed with the
``list-projects`` command:

.. code-block:: console

    $ flux account list-projects

    project_id | project | usage
    -----------+---------+------
    1          | *       | 0.0  
    2          | bronze  | 0.0  
    3          | silver  | 0.0  
    4          | gold    | 0.0

.. note::

    You do not need to manually add the ``*`` project - this project is added
    when the flux-accounting database is first created and automatically added
    to every association.

******************************
Associating Jobs With Projects
******************************

Example 1: Default Projects
***************************

Projects do not need to be added to an association in order for them to be able
to submit and run jobs, even if projects are configured in the flux-accounting
database. By default, their jobs will show up with a ``"*"`` project name:

.. code-block:: console

    $ flux account view-job-records
    UserID     JobID          ...    Project    Bank                
    50002      23773315072    ...    *          A

Example 2: Manually Defined Projects
************************************

Once projects are defined in the ``project_table``, they can be assigned
to associations:

.. code-block:: console

    $ flux account add-user --username=user_1 --bank=A --projects=bronze

The association's list of accessible projects then becomes ``["bronze", "*"]``
with a default project of ``"bronze"``. So, if this association were to submit
and run jobs without specifying a project, it would fall under the ``"bronze"``,
project which can be seen from the job's
`jobspec <https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_14.html>`_:

.. code-block:: json

    "attributes": {
      "system": {
        "project": "bronze"
      }
    }

This job (and other jobs submitted under the ``"bronze"`` project) can then be
filtered with the ``view-job-records`` command:

.. code-block:: console

    $ flux account view-job-records --project=bronze
    UserID     JobID          ...    Project    Bank                
    50001      19998441472    ...    bronze     A  

Example 3: Multiple Projects
****************************

If an association belongs to multiple projects:

.. code-block:: console

    $ flux account add-user --username=user_2 --bank=A --projects=bronze,silver

they can specify which project they want to run jobs under by setting this
attribute at submission:

.. code-block:: console

    $ flux submit -S project=silver my_job

