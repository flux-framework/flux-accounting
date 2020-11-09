flux-accounting version 0.4.0 - 2020-11-06
------------------------------------------

#### Fixes

* `view-job-records` subcommand parameters adjusted to be unpacked as a dictionary (#55)

* Move `view_job_records()` and its helper functions into its own Python module (#57)

#### Features

* Add a library that provides a weighted tree-based fairness (#65)

* Add autogen, automake tools to flux-accounting repo (#65)

flux-accounting version 0.3.0 - 2020-09-30
------------------------------------------

#### Fixes

* `bank_table`'s primary key is now a fixed type (#42)

* `bank_table`'s subcommands no longer impose constraints on values of shares (#44)

* `print-hierarchy`'s format improved to represent a bank and user hierarchy (#51)

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
