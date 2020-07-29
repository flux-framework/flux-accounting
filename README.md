_NOTE: The interfaces of flux-accounting are being actively developed and are not yet stable. The Github issue tracker is the primary way to communicate with the developers._

## flux-accounting

Development for a bank/accounting interface for the Flux resource manager. Writes and saves user account information to persistent storage using Python's SQLite3 API.

### Build Requirements

flux-accounting requires the following packages to build:

| centos8       | ubuntu      | version |
| ------        | --------    | ------- |
| python3-devel | python3-dev | >= 3.6  |
| python3-pip   | python3-pip | 20.0.2  |
| tox           | tox         | 3.15.0  |

### Install Instructions

You can install the dependencies required by flux-accounting as well as the package itself to be recognized by Flux's command driver `flux(1)` with `make`.

1. Set your **FLUX_INSTALL_PREFIX** environment variable to point to flux-core's installation target:

```
$ export FLUX_INSTALL_PREFIX = ~/path/to/flux-core/install/
```

2. Pull down and install the flux-accounting repo:

```
$ git clone https://github.com/flux-framework/flux-accounting
$ cd flux-accounting/
$ make install
```

3. Run flux-accounting's commands:

```
$ flux account -h
usage: flux-account.py [-h] {view-user,add-user,delete-user,edit-user} ...

Description: Translate command line arguments into SQLite instructions for the
Flux Accounting Database.

positional arguments:
  {view-user,add-user,delete-user,edit-user}
                        sub-command help
    view-user           view a user's information in the accounting database
    add-user            add a user to the accounting database
    delete-user         remove a user from the accounting database
    edit-user           edit a user's value

optional arguments:
  -h, --help            show this help message and exit
```

### Test Instructions

Run the unit tests with `tox` to ensure the correctness of this package on your platform:

```
$ tox
python3.6 run-test: commands[0] | python -m unittest discover -b
....
----------------------------------------------------------------------
Ran 4 tests in 0.008s

OK
_______________________________summary _______________________________
  python3.6: commands succeeded
  congratulations :)
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
 python3.6 run-test: commands[0] | python -m unittest discover -b
.........
----------------------------------------------------------------------
Ran 9 tests in 0.035s

OK
___________________________________ summary ____________________________________
  python3.6: commands succeeded
  congratulations :)
Removing intermediate container 45479512d947
 ---> f29dd2ca5958
Successfully built f29dd2ca5958
```

### User Account Information

The accounting table in this database stores information like user name and ID, the account to submit jobs against, an optional parent account, the shares allocated to the user, as well as static limits, including max jobs submitted per user at a given time and max wall time per job per user.

### Interacting With the Accounting DB

There are two ways you can interact with the tables contained in the Accounting DB. The first way is to launch into an interactive SQLite shell. From there, you can open the database file and interface with any of the tables using SQLite commands:

```
$ sqlite3 path/to/FluxAccounting.db
SQLite version 3.24.0 2018-06-04 14:10:15
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.

sqlite> .tables
association_table
```

To get nicely formatted output from queries (like headers for the tables and proper spacing), you can also set the following options in your shell:

```
sqlite> .mode columns
sqlite> .headers on
```

This will output queries like the following:

```
sqlite> SELECT * FROM association_table;
creation_time  mod_time    deleted     user_name   admin_level  account     parent_acct  shares      max_jobs    max_wall_pj
-------------  ----------  ----------  ----------  -----------  ----------  -----------  ----------  ----------  -----------
1589225734     1589225734  0           fluxuser    1            acct        pacct        10          100         60  
```

The second way is to use flux-accounting's command line arguments. You can pass in a path to the database file, or be in the same directory where the database file (**FluxAccounting.db**) is located:

```
$ flux account -h

usage: flux-account.py [-h] {view-user,add-user,delete-user,edit-user} ...

Description: Translate command line arguments into SQLite instructions for the
Flux Accounting Database.

positional arguments:
  {view-user,add-user,delete-user,edit-user}
                        sub-command help
    view-user           view a user's information in the accounting database
    add-user            add a user to the accounting database
    delete-user         remove a user from the accounting database
    edit-user           edit a user's value

optional arguments:
  -h, --help            show this help message and exit
```

With flux-accounting's command line tools, you can view a user's account information, add and remove users to the accounting database, and edit an existing user's account information:

```
$ flux account view-user fluxuser

creation_time    mod_time  deleted user_name  admin_level     account parent_acct  shares  max_jobs  max_wall_pj
   1595438356  1595438356        0  fluxuser            1        acct       pacct       1       100           60
```
