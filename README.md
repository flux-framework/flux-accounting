[![Build Status](https://travis-ci.org/flux-framework/flux-accounting.svg?branch=master)](https://travis-ci.org/flux-framework/flux-accounting)
[![codecov](https://codecov.io/gh/flux-framework/flux-accounting/branch/master/graph/badge.svg)](https://codecov.io/gh/flux-framework/flux-accounting)

_NOTE: The interfaces of flux-accounting are being actively developed and are not yet stable. The Github issue tracker is the primary way to communicate with the developers._

## flux-accounting

Development for a bank/accounting interface for the Flux resource manager. Writes and saves user account information to persistent storage using Python's SQLite3 API.

### Build Requirements

flux-accounting requires the following Python packages to build:

| Package Name | Version    |
| ------------ | ---------- |
| pandas       | >= 0.24.1  |

### Install Instructions

##### Building From Source

```console
./autogen.sh
./configure
make -j
make check
```

To configure flux-accounting with a specific version of Python, pass the `PYTHON_VERSION` environment variable on the `./configure` line (_note: flux-accounting needs to be configured against the same version of Python as flux-core that it is configured against; this is the default behavior of `./configure` if you choose the same prefix for flux-core and flux-accounting_):

```console
PYTHON_VERSION=3.7 ./configure
```

Run flux-accounting's commands:

```
usage: flux-account.py [-h] [-p PATH] [-o OUTPUT_FILE]
                       {view-user,add-user,delete-user,edit-user,view-job-records,create-db,add-bank,view-bank,delete-bank,edit-bank,print-hierarchy} ...

Description: Translate command line arguments into SQLite instructions for the Flux Accounting Database.

positional arguments:
  {view-user,add-user,delete-user,edit-user,view-job-records,create-db,add-bank,view-bank,delete-bank,edit-bank,print-hierarchy}
                        sub-command help
    view-user           view a user's information in the accounting database
    add-user            add a user to the accounting database
    delete-user         remove a user from the accounting database
    edit-user           edit a user's value
    view-job-records    view job records
    create-db           create the flux-accounting database
    add-bank            add a new bank
    view-bank           view bank information
    delete-bank         remove a bank
    edit-bank           edit a bank's allocation
    print-hierarchy     print accounting database

optional arguments:
  -h, --help            show this help message and exit
  -p PATH, --path PATH  specify location of database file
  -o OUTPUT_FILE, --output-file OUTPUT_FILE
                        specify location of output file
```

To run the unit tests in a Docker container, you can use `docker build -f <path/to/Dockerfile> .` from the flux-accounting directory:

```
$ docker build -f accounting/test/docker/ubuntu/Dockerfile.ubuntu .
Sending build context to Docker daemon  299.9MB
Step 1/5 : FROM ubuntu:latest
 ---> 1d622ef86b13
Step 2/5 : LABEL maintainer="Christopher Moussa <moussa1@llnl.gov>"
 ---> Using cache
 ---> bdbc2ff632a5
Step 3/5 : ADD . src/
 ---> 7da92dbd8852
 .
 .
 .
 Step 5/5 : RUN cd src/   && pip3 install -r requirements.txt   && tox
 .
 .
 .
 Installing collected packages: pytz, numpy, six, python-dateutil, pandas
 Successfully installed numpy-1.19.4 pandas-0.25.3 python-dateutil-2.8.1 pytz-2020.4 six-1.15.0
 .....................................
 ----------------------------------------------------------------------
 Ran 37 tests in 0.516s

 OK
```

### User Account Information

The accounting table in this database stores information like user name and ID, the bank to submit jobs against, the shares allocated to the user, as well as static limits, including max jobs submitted per user at a given time and max wall time per job per user.

### Interacting With the Accounting DB

There are two ways you can interact with the tables contained in the Accounting DB. The first way is to launch into an interactive SQLite shell. From there, you can open the database file and interface with any of the tables using SQLite commands:

```
$ sqlite3 path/to/FluxAccounting.db
SQLite version 3.24.0 2018-06-04 14:10:15
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.

sqlite> .tables
association_table bank_table
```

To get nicely formatted output from queries (like headers for the tables and proper spacing), you can also set the following options in your shell:

```
sqlite> .mode columns
sqlite> .headers on
```

This will output queries like the following:

```
sqlite> SELECT * FROM association_table;
creation_time  mod_time    deleted     username    admin_level  bank        shares      max_jobs    max_wall_pj
-------------  ----------  ----------  ----------  -----------  ----------  ----------  ----------  -----------
1605309320     1605309320  0           fluxuser    1            foo         1           1           60       
```

The second way is to use flux-accounting's command line arguments. You can pass in a path to the database file, or it will default to the "compiled-in" path of `${prefix}/var/FluxAccounting.db`.

With flux-accounting's command line tools, you can view a user's account information, add and remove users to the accounting database, and edit an existing user's account information:

```
$ flux account view-user fluxuser

creation_time    mod_time  deleted  username  admin_level   bank   shares  max_jobs  max_wall_pj
   1595438356  1595438356        0  fluxuser            1    foo        1       100           60
```
