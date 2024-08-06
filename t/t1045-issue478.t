#!/bin/bash

test_description='test calling view-user with the --list-banks optional argument'

. `dirname $0`/sharness.sh

mkdir -p conf.d

ACCOUNTING_DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB, start flux-accounting service' '
	flux account -p ${ACCOUNTING_DB} create-db &&
	flux account-service -p ${ACCOUNTING_DB} -t
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root bankA 1 &&
	flux account add-bank --parent-bank=root bankB 1 &&
	flux account add-bank --parent-bank=root bankC 1
'

test_expect_success 'add a user' '
	flux account add-user --username=testuser --bank=bankA &&
	flux account add-user --username=testuser --bank=bankB &&
	flux account add-user --username=testuser --bank=bankC
'

test_expect_success 'call view-user --list-banks' '
	flux account view-user testuser --list-banks > banks.out &&
	grep "bankA" banks.out &&
	grep "bankB" banks.out &&
	grep "bankC" banks.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_expect_success 'remove flux-accounting DB' '
	rm ${ACCOUNTING_DB}
'

test_done
