#!/bin/bash

test_description='test max-preempt-after values when adding/editing banks'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add root bank to the DB' '
	flux account add-bank root 1
'

test_expect_success 'add a sub bank with max-preempt in seconds' '
	flux account add-bank --parent-bank=root --max-preempt-after=60s A 1 &&
	flux account view-bank A > A.test &&
	grep "\"max_preempt_after\": 60.0" A.test
'

test_expect_success 'add a sub bank with max-preempt in hours' '
	flux account add-bank --parent-bank=root --max-preempt-after=1h B 1 &&
	flux account view-bank B > B.test &&
	grep "\"max_preempt_after\": 3600.0" B.test
'

test_expect_success 'add a sub bank with max-preempt in days' '
	flux account add-bank --parent-bank=root --max-preempt-after=1d C 1 &&
	flux account view-bank C > C.test &&
	grep "\"max_preempt_after\": 86400.0" C.test
'

test_expect_success 'add a sub bank with no max-preempt specified' '
	flux account add-bank --parent-bank=root D 1 &&
	flux account view-bank D > D.test &&
	grep "\"max_preempt_after\": null" D.test
'

test_expect_success 'trying to add a sub bank with a bad FSD will raise an error' '
	test_must_fail flux account add-bank \
		--parent-bank=root \
		--max-preempt-after=foo E 1 > error.out 2>&1 &&
	grep "add-bank: ValueError: invalid Flux standard duration" error.out
'

test_expect_success 'edit max-preempt-after for a bank' '
	flux account edit-bank A --max-preempt-after=200s &&
	flux account view-bank A > A_edited.test &&
	grep "\"max_preempt_after\": 200.0" A_edited.test
'

test_expect_success 'clear max-preempt-after for a bank' '
	flux account edit-bank A --max-preempt-after=-1 &&
	flux account view-bank A > A_cleared.test &&
	grep "\"max_preempt_after\": null" A_cleared.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
