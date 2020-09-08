flux-accounting version 0.2.0 - 2020-08-31
------------------------------------------

This release adds a new table to the flux-accounting database and a front end to flux-core's job-archive.

#### Features

* Add a new table `bank_table` that stores bank information for users to charge jobs against.

* Add a front-end interface to flux-core's job-archive to fetch job record information and sort it with customizable parameters, such as by username, before or after a specific time, or with a specific job ID.

flux-accounting version 0.1.0 - 2020-07-29
------------------------------------------

Initial release.

#### Features

* Create an accounting database which stores user account information. Can interact with database through SQLite shell or
through a command line interface to add and remove users, edit account values, and view account information.

* Add **Makefile** to allow flux-accounting to be installed alongside flux-core so that flux-accounting commands can be picked up by Flux's command driver.
