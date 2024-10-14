[![ci](https://github.com/flux-framework/flux-accounting/workflows/ci/badge.svg)](https://github.com/flux-framework/flux-accounting/actions?query=workflow%3A.github%2Fworkflows%2Fmain.yml)
[![codecov](https://codecov.io/gh/flux-framework/flux-accounting/branch/master/graph/badge.svg)](https://codecov.io/gh/flux-framework/flux-accounting)

_NOTE: The interfaces of flux-accounting are being actively developed and are
not yet stable. The Github issue tracker is the primary way to communicate with
the developers._

## flux-accounting

Development for a bank/accounting interface for the Flux resource manager.
Writes and saves user account information to persistent storage using Python's
SQLite3 API. Calculates fair-share values for users and banks based on
historical job data. Generates job priority values for users with a multi-factor
priority plugin.

### Install Instructions

For instructions for using a VSCode Development Container, see [this document in flux-core](https://github.com/flux-framework/flux-core/blob/master/vscode.md). You'll want to create the environment
and proceed with the steps below to build.

##### Building From Source

```console
./autogen.sh
./configure --localstatedir=/var/
make -j
make check
```

To configure flux-accounting with a specific version of Python, pass the
`PYTHON_VERSION` environment variable on the `./configure` line (_note: flux-
accounting needs to be configured against the same version of Python as
flux-core that it is configured against; this is the default behavior of
`./configure` if you choose the same prefix for flux-core and flux-accounting_):

```console
PYTHON_VERSION=3.7 ./configure --localstatedir=/var/
```

### Testing

To run the unit tests in a Docker container, or launch into an interactive container on your local machine, you can run `docker-run-checks.sh`:

```
$ ./src/test/docker/docker-run-checks.sh --no-cache --no-home -I --
Building image el8 for user <username> <userid> group=20
[+] Building 0.7s (7/7) FINISHED

.
.
.

mounting /Users/moussa1/src/flux-framework/flux-accounting as /usr/src
[moussa1@docker-desktop src]$
```

### User and Bank Information

The accounting tables in this database stores information like username and
ID, banks to submit jobs against, allocated shares to the user, as well as
static limits, including a max number of running jobs at a given time and
a max number of submitted jobs per user/bank combo.

### Interacting With the Accounting DB

In order to add, edit, or remove information from the flux-accounting database,
you must also have read/write access to the directory that the DB file resides
in. The [SQLite documentation](https://sqlite.org/omitted.html) states:

> Since SQLite reads and writes an ordinary disk file, the only access
permissions that can be applied are the normal file access permissions of the
underlying operating system.

There are two ways you can interact with the tables contained in the Accounting
DB. The first way is to launch into an interactive SQLite shell. From there, you
can open the database file and interface with any of the tables using SQLite
commands:

```
$ sqlite3 path/to/FluxAccounting.db
SQLite version 3.24.0 2018-06-04 14:10:15
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.

sqlite> .tables
association_table bank_table
```

To get nicely formatted output from queries (like headers for the tables and
proper spacing), you can also set the following options in your shell:

```
sqlite> .mode columns
sqlite> .headers on
```

This will output queries like the following:

```
sqlite> SELECT * FROM association_table;
creation_time  mod_time    deleted     username    bank        shares      max_jobs    max_wall_pj
-------------  ----------  ----------  ----------  ----------  ----------  ----------  -----------
1605309320     1605309320  0           fluxuser    foo         1           1           60       
```

The second way is to use flux-accounting's command line arguments. You can pass in
a path to the database file, or it will default to the "compiled-in" path of
`${prefix}/var/FluxAccounting.db`.

With flux-accounting's command line tools, you can view a user's account
information, add and remove users to the accounting database, and edit an existing
user's account information:

```
$ flux account view-user fluxuser

creation_time    mod_time  deleted  username  bank   shares  max_jobs  max_wall_pj
   1595438356  1595438356        0  fluxuser  foo         1       100           60
```

Multiple rows of data can be loaded to the database at once using `.csv` files
and the `flux account pop-db` command. Run `flux account pop-db --help` for
`.csv` formatting instructions.

User and bank information can also be exported from the database using the
`flux account export-db` command, which will extract information from both the
user and bank tables and place them into `.csv` files.

#### Release

SPDX-License-Identifier: LGPL-3.0

LLNL-CODE-764420
