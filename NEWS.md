flux-accounting version 0.52.0 - 2025-09-30
-------------------------------------------

#### Fixes

* `view-user`/`edit-user`: use `"unlimited"` to display and set `max_nodes` and
`max_cores` to their default values (#751)

* `update-usage`: add `-v/--verbose` option (#753)

* plugin: check dependencies of held jobs after `flux account-priority-update`
(#752)

* plugin: remove job from `held_jobs` if cancelled (#765)

##### Features

* plugin: add more information returned in output of `flux jobtap query` (#737)

* util: add `parse_timestamp()` function (#740)

* `jobs` command: add more options to filter jobs by (#741)

* `view-job-records`: add filter for duration delta of jobs (#742)

* `list-users`: extend command to search for multiple values per filter (#745)

#### Documentation

* doc: expand example job priority calculation (#747)

#### Testsuite

* testsuite: stop using `flux job cancelall` (#743)

* t1043: add `wait-event` for jobs after cancelling (#746)

* mergify: disable temporary PR branches (#762)

* mergify: remove queue_conditions, status-success checks (#767)

flux-accounting version 0.51.0 - 2025-09-03
-------------------------------------------

#### Fixes

* plugin: don't initialize "queues" map when checking limits (#734)

flux-accounting version 0.50.0 - 2025-09-02
-------------------------------------------

#### Fixes

* plugin: improve error message context in job.validate (#712)

* cmd: remove `--output-file` argument (#716)

* formatter: remove `HierarchyFormatter` class (#717)

* `update-fshare`: wrap `UPDATE`s in single transaction, enable `PRAGMA`s to
enable concurrency (#720)

* `scrub-old-jobs`: add `0` return code on successful runs of
`scrub_old_jobs()` (#721)

* `update-usage`: condense `SELECT` query to fetch recent job usage factor, use
row names, drop unused function arg (#722)

* `update-usage`: remove extra `SELECT` query in favor of retrieving past job
usage information beforehand (#723)

* `update-usage`: remove `SELECT` query on `jobs` table for every association
(#725)

* `update-usage`: add `.rollback()` in case of error (#726)

* github: update crate-ci version (#727)

#### Features

* `jobs`: add duration fields to `jobs` table, return both requested and actual
duration in `view-job-records` (#718)

* `view-job-records`: add filters for requested duration and actual duration in
`jobs` table (#719)

* `view-bank`: add `-c/--concise` option (#730)

* python: add general utility file for duplicate function definitions, general
helper functions (#731)

#### Testsuite

* testsuite: don't load deprecated barrier module (#724)

flux-accounting version 0.49.0 - 2025-08-04
-------------------------------------------

#### Fixes

* plugin: reject jobs that exceed an association's or queue's max resources
limits (#710)

flux-accounting version 0.48.0 - 2025-08-01
-------------------------------------------

#### Features

* database: add `max_nodes` column to `queue_table` (#695)

* priority-update: send `max_nodes_per_assoc` to plugin, add
`max_nodes_per_assoc` attribute to `Queue` class (#702)

* plugin: add `QueueUsage` class to track an association's node usage per-queue
(#703)

* command: add `edit-all-users` command (#700)

* plugin: add enforcement of a per-queue max nodes limit (#704)

* bindings: add `db_version()` function, use it across scripts that check DB
version (#684)

* `view-user`: add `-J/--job-usage` optional arg (#706)

#### Fixes

* update-usage: move one-time SQL query out of `for`-loop, combine
per-association queries (#680)

* `add-user`: remove extra `.commit()` when `INSERT`-ing values into
`association_table` (#681)

* plugin: remove unused function arguments from `priority_calculation ()`
(#687)

* `jobs`: use fair-share at priority calculation instead of association's
current fair-share (#686)

* flux-accounting service: use `DB_SCHEMA_VERSION` constant instead of
hard-coded value (#683)

* plugin: shorten line that is greater than 80 characters (#696)

* `bindings/`: remove job-usage documentation (#705)

* `BankFormatter`: reduce duplicate traversal code (#676)

#### Documentation

* doc: add note about case sensitivity for names (#698)

* doc: update `man(1)` page for `edit-user` (#701)

* doc: add flux-accounting "Module Structure" page (#707)

flux-accounting version 0.47.0 - 2025-06-30
-------------------------------------------

#### Features

* plugin: enforce max resource limits per-association (#562)

* database: add new table to store priority factors and their weights (#665)

* plugin: unpack priority factor weights from database (#670)

* plugin: add weight for `urgency` factor, update docs with new equation (#673)

* commands: add new `jobs` command to view priority breakdowns of jobs (#674)

* database: add graph commands for displaying job usage values for
associations, banks (#677)

#### Fixes

* flux-accounting service: use `.get()` instead of direct key access (#653)

* update-usage: remove extra `.commit()` from helper function (#675)

* job-usage update: move update out of flux-accounting service and into own
script (#657)

#### Documentation

* doc: add `man(1)` pages for priority factor commands (#672)

* doc: add new "Limits" page (#667)

* doc: add `man(1)` page for `view-job-records` (#669)

* doc: update top-level flux-account man page with project command links (#668)

flux-accounting version 0.46.0 - 2025-06-02
-------------------------------------------

#### Features

* `bank_table`: add `priority` column (#643)

* plugin: add `Bank` class, send bank priority information to plugin (#645)

* plugin: utilize `bank` priority when calculating priority for a job (#647)

#### Documentation

* doc: remove `jinja2 < 3.1.0` requirement (#646)

* doc: drop `sphinx < 6.0.0` (#648)

* doc: update docs with bank factor (#649)

* doc: add note about active per-queue limits (#652)

#### Testsuite

* codecov: include Python bindings in codecov report (#644)

flux-accounting version 0.45.0 - 2025-05-21
-------------------------------------------

#### Fixes

* bindings: remove redundant `try/except` blocks (#625)

* `.gitignore`: add files to `.gitignore` (#627)

* `list-*` commands: make table output default (#626)

* `calc_usage_factor()`: add update of current usage when no new jobs are
found in new half-life period (#630)

* `update-usage`: fix usage aggregation in multi-level bank hierarchies (#632)

* `update-usage`: add INFO-level logging (#628)

* python: improve logger format in `update-usage`, create module-level logger
in `create-db` (#633)

#### Documentation

* doc: add `man(1)` pages for project commands (#634)

#### Testsuite

* github: upgrade codecov-action to v5 (#629)

flux-accounting version 0.44.0 - 2025-05-06
-------------------------------------------

#### Fixes

* plugin: create label for `dependency_remove < 0` (#606)

* plugin: improve `Queue` class (#609)

* `delete-queue`: add warning statement when deleting a queue still referenced
by associations (#612)

* `construct_hierarchy()`: use column names (#614)

* plugin: improve how dependency logic works with new `Job` class (#610)

* `flux-account`: add `@CLIMain` decorator (#621)

* `flux-account`: standardize prefixes for error messages (#622)

#### Features

* plugin: add a new `Job` class (#608)

* `add-user`: add `--fairshare` as an optional argument (#615)

* `list-users`: add `--default-project` optional argument, man page (#616)

* `add-user`: add `--default-project` as an optional argument (#619)

#### Documentation

* `view-*` man pages: add `-o/--format` optional arg (#611)

* doc: add `man(1)` pages for `*-queue` commands (#613)

* `add-user(1)`: clarify how default project is set (#618)

flux-accounting version 0.43.0 - 2025-04-01
-------------------------------------------

#### Fixes

* fair-share calculation: change `shares`, `usage` types to more appropriate
types (#585)

* plugin: return more specific error messages when updating bank attribute
(#590)

* `apply_decay_factor ()`: fix iteration through usage periods, actually
`commit` SQL statements (#594)

* mf_priority: update jj library from flux-core (#603)

* plugin: clean up error handling, comments in `job.state.depend` (#605)

#### Features

* plugin: add enforcement of max running jobs limit for a queue per-association
(#491)

* python: create new `QueueFormatter` class, refactor `view_queue()` to use new
class (#586)

* cmd: add `list-queues` command (#588)

* cmd: add new `list-users` command (#597)

* `view-*`/`list-*` commands: add `-o/--format` optional argument (#600)

* bindings: add `ProjectFormatter` subclass, `-o/--format` options to
`view-project`/`list-projects` (#602)

#### Testsuite

* ci: update Ubuntu version for GitHub actions (#584)

#### Documentation

* doc: add health/sanity checklist for flux-accounting (#592)

flux-accounting version 0.42.0 - 2025-02-11
-------------------------------------------

#### Fixes

* python: use column names when accessing results of a query instead of row
indices (#579)

* `update-fshare`: change job usage variable from 32-bit `int` to `double`
(#581)

#### Features

* doc: add man(1) page support, entries for DB administration subcommands
(#538)

* `formatter`: add new `JobsFormatter` class, restructure view-job-records to
use new class (#563)

flux-accounting version 0.41.0 - 2025-02-04
-------------------------------------------

#### Fixes

* `view-job-records`: accept multiple timestamp formats for `after-start-time`,
`before-end-time` optional args (#567)

* `view-job-records --jobid`: accept all Flux job ID formats (#566)

* `t/Makefile.am`: add missing line continuation (`\`) character (#570)

* `edit-user`: make `fairshare` an editable field for an association (#569)

* `job.state.priority`: remove raising exception when no aux item found (#568)

#### Features

* doc: add section on configuring queue permissions (#550)

* python: create new `BankFormatter` subclass, restructure view-bank to use new
class (#525)

* `view-user`: create new `AssociationFormatter` subclass for viewing
associations (#527)

* `association_table`: add `max_cores` attribute, send information to plugin
(#560)

* plugin: track the resources used across all of an association's running jobs
(#561)

* `view-user`: add a new `--list-banks` optional argument (#479)

* doc: add fair-share documentation (#536)

* `delete-user`: add `--force` option to actually remove a row from the
`association_table` (#572)

* `delete-bank`: add `--force` option to actually remove a row from the
`bank_table` (#573)

* doc: add note about permanently deleting rows with `--force`, update
`view-user` examples (#574)

#### Testsuite

* testsuite: pull in valgrind suppression from core (#546)

* testsuite: add longer test descriptions for some of the more complex test
scenarios (#548)

#### CI

* github: fix ubuntu version for `"python-format"` action (#547)

flux-accounting version 0.40.0 - 2024-12-03
-------------------------------------------

#### Fixes

* `list-banks`: use `AccountingFormatter` class (#524)

* `add-user`: make `--username` and `--bank` required arguments (#532)

* `edit-user`: unify reset behavior, `**kwargs` for editable fields (#535)

#### Features

* `view-job-records`: add `--bank` filter option (#533)

* doc: add example on configuring priorities for queues (#542)

#### Testsuite

* t: change which user is deleted from `association_table` (#528)

#### CI

* ci(mergify): upgrade configuration to current format (#537)

flux-accounting version 0.39.0 - 2024-11-05
-------------------------------------------

#### Fixes

* `view-user`: make "parsable" spelling consistent (#494)

* projects: fix unit tests for project subcommands, `--projects` reset
capability (#495)

* plugin: add callback prefixes to exception messages (#499)

* `add-bank`: add a check when adding a root bank (#509)

* fetch-job-records: set `max_entries=0` (#516)

* `view-user --parsable`: improve output formatting (#514)

* `flux-account.py`: get rid of dictionary initialization (#512)

* `__init__.py`: fix formatting of constants (#521)

* `view_jobs()`: adjust helper function to actually return a string (#522)

#### Features

* command suite: add new `list-projects` command (#496)

* ci: add spellchecker to flux-accounting (#504)

* python: add `AccountingFormatter` class, SQLite utility file (#520)

#### Testsuite

* `.gitignore`: add built docs, sharness test results (#511)

* t: skip t1011 if job-archive module not detected, add new tests for 
`fetch-job-records` (#518)

#### Documentation

* doc: add note about manually loading plugin (#500)

* doc: add ReadTheDocs support for flux-accounting (#501)

* guide: add note about configuring factor weights (#505)

* doc: add "Database Administration" section, update README to point to docs
site (#506)

* doc: reorganize top-level site, add License and Support page (#510)

* doc: add priority equation to accounting guide (#513)

flux-accounting version 0.38.0 - 2024-10-01
-------------------------------------------

#### Fixes

* JobRecord: remove `username` from `__init__()` of JobRecord object (#489)

* `job.state.inactive`: add `return -1` to exception (#492)

#### Features

* plugin: add project validation/annotation (#443)

* `view-job-records`: add `--project` filter option (#490)

flux-accounting version 0.37.0 - 2024-09-03
-------------------------------------------

#### Fixes

* plugin: move `flux_respond ()` to end of functions (#431)

* Makefile: remove left over compile instructions for `flux_account_shares`
(#482)

* configure: add `jansson` as a dependency check (#484)

* doc: add example error message when creating DB after starting systemd
service (#485)

#### Features

* plugin: add instance owner info to plugin (#477)

* cmd: add `export-db` as a `flux account` command (#486)

* cmd: add `pop-db` as a `flux account` command (#487)

flux-accounting version 0.36.0 - 2024-08-06
-------------------------------------------

#### Fixes

* python: change function descriptions to follow docstring convention (#468)

* python: convert more function descriptions to docstring format (#470)

* src: remove `flux_account_shares.cpp` in favor of just using `-t` option with
`view-bank` (#471)

* `fetch-job-records`: add integrity check for records (#475)

#### Features

* `bank_table`: add a new `list-banks` command (#473)

flux-accounting version 0.35.0 - 2024-07-10
-------------------------------------------

#### Fixes

* t: move python unit tests to `t/python/` directory (#462)

* python: clean job-archive interface code (#463)

* `conf.update`: add missing bracket in format string (#465)

#### Testsuite

* testsuite: fix on systems with flux-accounting already installed (#467)

flux-accounting version 0.34.0 - 2024-07-02
-------------------------------------------

#### Fixes

* `inactive_cb ()`: remove unused iterator variables (#457)

* plugin: initialize factor weights on plugin load (#458)

* job archive interface: clean up a couple helper functions (#460)

#### Features

* database: add the ability to remove old records from `jobs` table (#459)

flux-accounting version 0.33.0 - 2024-06-04
-------------------------------------------

#### Fixes

* job-archive interface: wrap job usage updates into a single SQL transaction (#452)

* database: update schema version (#453)

#### Features

* plugin: add configurable priority factors via TOML `conf.update` (#295)

#### Testsuite

* testsuite: change check for specific job states (#393)

* testsuite: replace `flux job cancel` --> `flux cancel` (#454)

flux-accounting version 0.32.0 - 2024-05-13
-------------------------------------------

#### Fixes

* repo: add `pkg.m4`, checks for flux-core libs (#441)

#### Features

* flux-accounting: add a local job-archive (#357)

* plugin: add `max_nodes` as an attribute per-association in plugin (#437)

* repo: create a `doc` folder, add flux-accounting guide (#446)

#### Testsuite

* t: update description of sharness tests (#447)

* testsuite: enable guest access to testexec (#449)

flux-accounting version 0.31.0 - 2024-04-02
-------------------------------------------

#### Fixes

* plugin: move flux-accounting-specific helper functions, remove unused ones
(#427)

* plugin: improve `add_missing_bank_info ()` (#430)

* plugin: change `projects`->`assoc_projects` in `rec_update_cb ()` (#438)

#### Features

* plugin: add support for updating the bank of a pending job (#429)

* plugin: add project information to Association information in plugin (#434)

* `plugin.query`: add projects, def_project to the information returned (#435)

#### Testsuite

* t: add `active` column, move sample payloads (#432)

* t1029: remove brackets from `grep` tests (#433)

flux-accounting version 0.30.0 - 2024-03-04
-------------------------------------------

#### Fixes

* plugin: improve callback for `job.validate` (#415)

* plugin: move helper functions for `plugin.query` callback (#417)

* plugin: move `split_string ()` out of plugin code (#418)

* plugin: improve callback for `job.new` (#421)

* plugin: improve `job.update/job.update...queue` callbacks (#423)

* plugin: improve `job.state.priority` callback (#425)

#### Features

* plugin: add external `Association` class to be used in plugin (#412)

flux-accounting version 0.29.0 - 2024-01-08
-------------------------------------------

#### Fixes

* plugin: keep jobs in `PRIORITY` after reprioritization (#407)

* plugin: add callback specific for validating an updated queue (#399)

#### Testsuite

* feat: developer container environment (#398)

flux-accounting version 0.28.0 - 2023-10-02
-------------------------------------------

#### Fixes

* `edit-user`: fix default values for optional args (#382)

* plugin: improve check of internal user/bank map in `job.validate` (#386)

* plugin: move queue priority assignment to `job.new` callback (#388)

* `view-bank`: fix `-t` option for a sub bank with users in it (#395)

#### Features

* plugin: record bank name to jobspec in PRIORITY event (#301)

* plugin: add queue update validation (#389)

#### Testsuite

* load content module in rc scripts (#383)

* ci: remove `upload-tarball` step from workflow (#387)

* testsuite: allow sharness tests to be run by hand (#392)

flux-accounting version 0.27.0 - 2023-09-06
-------------------------------------------

#### Fixes

* `.cpp`: add `config.h` include to source code (#366)

* `.cpp`: wrap `"config.h"`, C headers in `extern "C"` (#368)

* python: remove empty `quotechar` argument from `csv.writer` object
initialization (#372)

* python: rename `rows` variable to something more descriptive (#374)

* plugin: check for `FLUX_JOB_STATE_NEW` in `validate_cb ()` (#378)

#### Testsuite

* build: add `make deb` target for test packaging (#363)

* t: reorganize `t1007-flux-account.t` into multiple sharness tests (#367)

* docker: transition `bionic` container to `jammy` (#369)

* t: add valgrind folder to flux-accounting (#373)

* ci: update github actions `main.yml` file (#375)

flux-accounting version 0.26.0 - 2023-07-07
-------------------------------------------

#### Fixes

* database: update DB schema version (#361)

#### Features

* bank_table: add new job_usage column (#359)

* `view-bank`: improve `-t` option (#359)

#### Testsuite

* t: add new Python test directory in `t/` (#358)

flux-accounting version 0.25.0 - 2023-05-04
-------------------------------------------

#### Fixes

* plugin: improve handling of submitted jobs based on data presence in
plugin (#347)

flux-accounting version 0.24.0 - 2023-05-02
-------------------------------------------

#### Fixes

* flux-accounting service: make certain commands accessible to all users (#330)

* flux-accounting service: change BindTo to BindsTo (#341)

* `view-user`: improve formatting of output of command (#342)

* `update-db`: fix SQLite statement when updating a table with no primary key
(#343)

#### Testsuite

* replace `flux mini` usage (#344)

flux-accounting version 0.23.1 - 2023-04-07
-------------------------------------------

#### Fixes

* flux-accounting service: change Requires to BindTo (#338)

flux-accounting version 0.23.0 - 2023-04-04
-------------------------------------------

#### Fixes

* bindings: raise error to caller (#327, #328, #329)

* plugin: clear queues on flux-accounting DB update (#334)

flux-accounting version 0.22.2 - 2023-03-14
-------------------------------------------

#### Fixes

* plugin: rework increment/decrement of running and active job counts for
associations (#325)

flux-accounting version 0.22.1 - 2023-03-10
-------------------------------------------

#### Fixes

* `edit-user`: make "userid" an editable field (#319)

* `view-*` commands: raise `ValueError` when item cannot be found in
flux-accounting DB (#320)

* `view-bank`: re-add `-t` option to command (#322)

flux-accounting version 0.22.0 - 2023-03-03
-------------------------------------------

#### Fixes

* `view-job-records`: fix arguments passed in via `flux-account-service.py` (#316)

#### Features

* Add new service for `flux account` commands (#308)

* Add systemd unit file for flux-accounting service (#315)

flux-accounting version 0.21.0 - 2022-12-12
-------------------------------------------

#### Features

* Add ability to edit the parent bank of a bank (#299)

#### Testsuite

* Do not assume queues default to stopped (#302)

* Stop all queues with `--all` option (#303)

flux-accounting version 0.20.1 - 2022-10-05
-------------------------------------------

#### Fixes

* Change `update-db` command to create temporary database in `/tmp` instead
of current working directory (#288)

flux-accounting version 0.20.0 - 2022-10-04
-------------------------------------------

#### Fixes

* Add additional exception messages to Python commands (#267)

* Improve dependency message for running jobs limit (#269)

* Clean up user subcommand functions (#271)

* Clean up bank subcommand functions (#275)

* Disable queue validation in multi-factor priority plugin on unknown queue,
no configured "default" queue after flux-core queue changes (#281)

* Change default values of "DNE" entry to allow multiple jobs to be submitted
(#286)

* Change install location of multi-factor priority plugin (#287)

#### Features

* Add database schema version to flux-accounting DB (#274)

* Add automatic DB upgrade to `flux account-priority-update` command if
flux-accounting database is out of date (#274)

flux-accounting version 0.19.0 - 2022-09-07
-------------------------------------------

#### Features

* Add new `plugin.query` callback to multi-factor priority plugin which returns
internal information about users and banks, active and running job counts, and
any held jobs at the time of the query (#264)

flux-accounting version 0.18.1 - 2022-08-09
-------------------------------------------

#### Fixes

* Fix `update-db` command to provide clearer exception messages when
the command fails to update a flux-accounting database (#258)

#### Features

* Add new tests for the `update-db` command for updating old versions
of a flux-accounting database (#258)

flux-accounting version 0.18.0 - 2022-08-02
-------------------------------------------

#### Fixes

* Fix `update-db` command to account for deleted columns when updating a
flux-accounting database (#252)

* Improve error message clarity from sqlite3.connect when running the
`update-db` command (#248)

#### Features

* Add ability to disable a user/bank combo in the multi-factor priority plugin
that prevents a user from submitting and running jobs (#254)

flux-accounting version 0.17.0 - 2022-06-23
-------------------------------------------

#### Fixes

* Disable requirement for a `default` queue (#237)

#### Features

* Add a new `max_nodes` column to the `association_table` which represents
the max number of nodes a user/bank combo can have across all of their
running jobs (#235)

* Add a sharness test for calculating job priorities of multiple users with
different `--urgency` values (#236)

* Add a new `export-db` command which extracts information from both the
`association_table` and `bank_table` into `.csv` files for processing (#243)

* Add a new `update-db` command which adds any new tables and/or adds any
new columns to existing tables in a flux-accounting database (#244)

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
