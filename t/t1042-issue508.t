#!/bin/bash

test_description='test trying to add more than one root bank to the bank_table'

. `dirname $0`/sharness.sh

mkdir -p conf.d

ACCOUNTING_DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB, start flux-accounting service' '
	flux account -p ${ACCOUNTING_DB} create-db &&
	flux account-service -p ${ACCOUNTING_DB} -t
'

test_expect_success 'add a root bank' '
	flux account add-bank root 1
'

test_expect_success 'adding a second root bank will raise a ValueError' '
	test_must_fail flux account add-bank second_root 1 > error.out 2>&1 &&
	grep "bank_table already has a root bank" error.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_expect_success 'remove flux-accounting DB' '
	rm ${ACCOUNTING_DB}
'

test_done
