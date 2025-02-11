#!/bin/bash

test_description='test updating fair-share for a DB with huge job usage values'

. `dirname $0`/sharness.sh
TEST_DB=$(pwd)/FluxAccountingTest.db

UPDATE_USAGE=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create small_no_tie flux-accounting DB' '
	flux account -p ${TEST_DB} create-db
'

test_expect_success 'start flux-accounting service on small_no_tie DB' '
	flux account-service -p ${TEST_DB} -t
'

test_expect_success 'add users/banks to DB' '
	flux account add-bank root 1000 &&
	flux account add-bank --parent-bank root bankA 1 &&
	flux account add-user --username leaf.1.1 --bank bankA
'

test_expect_success 'update usage and fair-share for the users/banks' '
	flux python ${UPDATE_USAGE} ${TEST_DB} leaf.1.1 19115069644.16
	flux account update-usage
'

test_expect_success 'ensure update-fshare works with a huge job usage value' '
	flux account-update-fshare -p ${TEST_DB}
'

test_expect_success 'remove flux-accounting DB' '
	rm ${TEST_DB}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
