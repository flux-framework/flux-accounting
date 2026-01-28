#!/bin/bash

test_description='make sure an error is raised when creating an invalid bank hierarchy structure'

. `dirname $0`/sharness.sh

mkdir -p config

DB=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association' '
	flux account add-user --username=user1 --userid=50001 --bank=A
'

# Associations can only be added to banks that do not have any sub-banks under
# them. Since the 'root' bank has a sub-bank under it (bank 'A'), this will
# fail.
test_expect_success 'adding an association under the same parent bank as a sub-bank fails' '
	test_must_fail flux account add-user --username=user1 --userid=50001 --bank=root > error_assoc.out 2>&1 &&
	grep "associations cannot be added to the same parent bank as a sub-bank" error_assoc.out
'

# Banks (particularly, sub-banks) can only be added under a parent that does
# not already have associations in it. Since bank 'A' has one association in
# it, this will fail.
test_expect_success 'adding a bank under the same parent bank that has associations in it fails' '
	test_must_fail flux account add-bank --parent-bank=A B 1 > error_bank.out 2>&1 &&
	grep "banks cannot be added to a bank that currently has associations in it" error_bank.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
