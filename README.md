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

#### Release

SPDX-License-Identifier: LGPL-3.0

LLNL-CODE-764420
