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

You can install the dependencies required by flux-accounting (located in **requirements.txt**) with the following command:

```
$ pip3 install -r requirements.txt
```

### Test Instructions

Run the unit tests with `tox` to ensure the correctness of this package on your platform::

```
$ tox
python3.6 run-test: commands[0] | python -m unittest discover
....
----------------------------------------------------------------------
Ran 4 tests in 0.008s

OK
_______________________________summary _______________________________
  python3.6: commands succeeded
  congratulations :)
```

##### user account information

The accounting table in this database stores information like user name and ID, the account to submit jobs against, an optional parent account, the shares allocated to the user, as well as static limits, including max jobs submitted per user at a given time and max wall time per job per user.
