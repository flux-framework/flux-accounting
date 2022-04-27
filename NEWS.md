flux-accounting version 0.16.0 - 2022-04-30
------------------------------------------

#### Fixes

* Fix memory corruption due to use-after-free of the "DNE" bank entry (#233)

#### Features

* Add queue priority to job priority calculation (#207)

flux-accounting version 0.15.0 - 2022-03-31
-------------------------------------------

#### Fixes

* Fix incorrect job usage calculation for users who belong to multiple banks (#219)

* Update the `pop-db` command to include the `max_active_jobs`, `max_running_jobs`
  limits defined in the `association_table` (#224)

* Remove the unused ‘deleted’ column from the `association_table` in the flux-accounting DB (#224)

* Fix the default value for the `--queues` optional argument in the `edit-user` command (#225)

#### Features

* Add an `rc1` script that populates multi-factor priority plugin with flux-accounting DB
information on instance startup or restart (#223)

* Allow multi-factor priority plugin to be loaded and hold jobs without user/bank
information (#227)

flux-accounting version 0.14.0 - 2022-02-28
-------------------------------------------

#### Fixes

* Fix incorrect listing of column names when printing table information in the flux-accounting database (#203)

* Fix `TypeError` when not specifying a value for an optional argument for the `update-usage` command (#209)

* Fix incorrect parsing of the `count_ranks()` helper function when updating job usage values (#211)

#### Features

* Add a new `max_active_jobs` limit for user/bank combos in the multi-factor priority plugin (#201)

* Add a new distcheck builder to flux-accounting CI (#206)

flux-accounting version 0.13.0 - 2022-01-31
-------------------------------------------

#### Fixes

* Improve sharness tests to use `flux account` commands directly in tests (#180)

* Change positional and optional arguments in `edit-user` command to align with other `edit-*` commands (#181)

* Fix bug in `view-user` preventing the ability to view more than one row if a user belonged to more than one bank (#187)

* Remove outdated `admin_level` column from association_table in flux-accounting database (#188)

* Fix incorrect listing of association_table headers in the `view-user` command (#193)

* Fix `UNIQUE constraint` failure when re-adding a previously deleted user to the same bank in the flux-accounting database (#193)

* Convert the `qos` argument into positional arguments for both the `view-qos` and `edit-qos` commands (#193)

#### Features

* Add new enforcement policy in multi-factor priority plugin to only count running jobs towards an "active" jobs counter (#177)

* Add section to top-level README on flux-accounting database permissions (#188)

* Add new optional arguments to `view-bank` command to view sub bank hierarchy trees or users belonging to a specific bank (#194)

* Add bulk database populate tool to upload multiple user or bank rows at one time via `.csv` file (#195)

flux-accounting version 0.12.0 - 2021-12-03
-------------------------------------------

#### Fixes

* Improve bulk update script by reducing number of sent payloads to just one payload containing all required data needed by multi-factor priority plugin (#167)

* Drop `ax_python_devel.m4` and adjust `configure.ac` since flux-accounting does not use `PYTHON_CFLAGS` or `PYTHON_LIBS` and rejects python `3.10.0` as too old (#173)

* Add LLNL code release number to flux-accounting (#175)

#### Features

* Add support for defining, configuring, and editing queues and its various limits within the flux-accounting database (#176)

flux-accounting version 0.11.0 - 2021-10-29
-------------------------------------------

#### Fixes

* Replace the "strict" merge mode with queue+rebase in Mergify (#158)

* Add missing installation of the Python bulk update script that sends updated database information to the priority plugin (#162)

* Change names of all automatic update scripts to fall under one prefix called "account" (#162)

* Change the default DB path for all flux-accounting subcommands (#170)

* Remove the positional argument for the `create-db` subcommand (#170)

* Unify the optional database path arguments for all of the `flux account` commands (#171)

#### Features

* Add new instructions to the top-level README on setting up the flux-accounting database, loading the priority plugin, and configuring the automatic update scripts (#157)

flux-accounting version 0.10.0 - 2021-09-30
-------------------------------------------

#### Fixes

* Fix bug in add-user where wrong number of arguments were passed to function (#140)

* Fix bug in edit-user to ensure an edit made in one user/bank row was only made in just that one row instead of in multiple rows in the flux-accounting database (#140)

#### Features

* Add a new front-end update script that will re-calculate users' fairshare values and update them in the flux-accounting database (#138)

* Add new Quality of Service table in the flux-accounting database, which will hold Quality of Services and their associated priorities (#143)

* Add new sharness tests for Python subcommands (#140)

* Remove pandas dependency from flux-accounting, which was required to build/install (#144)

flux-accounting version 0.9.0 - 2021-09-07
------------------------------------------

#### Fixes

* Fix bug where users couldn't be added due to a broken function header (#140)

* Fix bug where a bank's shares could not be edited (#140)

#### Features

* Add a new multi-factor priority plugin that will calculate and push a user's job priority using multiple factors (#122)

* Add a new external service that grabs flux-accounting database information and pushes it to the multi-factor priority plugin (#122)

* Add a max jobs limit to the priority plugin that will enforce a limit of active jobs on a user/bank combination in the flux-accounting database (#131)

* Add a new STDOUT writer class to write user/bank information from a flux-accounting database to STDOUT (#120)

flux-accounting version 0.8.0 - 2021-04-30
------------------------------------------

#### Fixes

* Updated headers of source files in the `fairness` directory (#113)

* Fixed module/dependency installation strategy of flux-accounting on the `bionic` Docker image (#114)

* Fixed bug where old job usage values incorrectly included old factors when applying a decay value (#118)

* Fixed bug where the all job usage factors were incorrectly updated multiple times in one half-life period (#118)

* Fixed bug where a historical job usage value was updated even in the case where no new jobs were found in the current half-life period (#118)

* Fixed bug where the last seen job timestamp was reset to 0 if no new jobs were found for a user (#118)

#### Features

* Added a new `fairshare` field to the `association_table` in a flux-accounting database (#116)

* Added a new `writer` class which will update associations with up-to-date fairshare information (#116)

    * Added a subclass `data_writer_db` which will write fairshare information to a flux-accounting SQLite database

* Added a new subcommand to `flux account` that calculates and updates historical job usage values for every association in the flux-accounting database (#118)

flux-accounting version 0.7.0 - 2021-04-02
------------------------------------------

#### Fixes

* Fixed `ModuleNotFound` error when running Python unit tests on Python `3.6` (#106)

* Removed shebang line from **flux-account.py** to prevent Python version mismatch errors (#101)

#### Features

* Added a new `reader` class which will read flux-accounting information and load it to a `weighted_tree` object (#103)

    * Added a subclass `data_reader_db` which will read and load information from a flux-accounting SQLite database

* Added a new flux subcommand: `flux shares`, which will output a flux-accounting database hierarchy containing user/bank shares and usage information (#109)

flux-accounting version 0.6.0 - 2021-01-29
------------------------------------------

#### Fixes

* Unused variables and imports removed, license in `src/fairness/` changed to LGPL (#90)

* Behavior of `delete-user`, `delete-bank` changed to keep job history of a user after they are removed from the flux-accounting DB (#92)

* `bank` argument added to the `delete-user` subcommand (#95)

#### Features

* `unittest.mock()` integrated with job-archive interface unit tests (#93)

* flux-accounting database can be loaded into weighted tree library to generate fairshare values for users (#97)

flux-accounting version 0.5.0 - 2020-12-18
------------------------------------------

#### Fixes

* `print-hierarchy`'s error output more graceful when there are no accounts (#62)

* `association_table`'s `user_name` field changed to `username` (#67)

* **accounting_cli.py**'s `account` option changed to `bank` (#70)

* variables in **print_hierarchy.cpp** moved from `global` scope (#71)

* Python code converted over to use autotools, TAP, and sharness (#73)

#### Features

* `print-hierarchy` added as a C++ implementation to weighted tree lib (#64)

* `delete-bank` recursively deletes sub banks and associations when a parent bank is deleted (#78)

* `calc_usage_factor()` calculates a user's historical job usage value based on their job history (#79)

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
