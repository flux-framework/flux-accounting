#!/bin/bash

test_description='test calling view-bank with --concise'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
UPDATE_USAGE_COL=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add some associations' '
	flux account add-user --username=user1 --userid=50011 --bank=A &&
	flux account add-user --username=user2 --userid=50012 --bank=A &&
	flux account add-user --username=user3 --userid=50013 --bank=B &&
	flux account add-user --username=user4 --userid=50014 --bank=B
'

test_expect_success 'call view-bank on the root bank without --concise' '
	flux account view-bank -t root > hierarchy_default.test &&
	grep "user1" hierarchy_default.test &&
	grep "user2" hierarchy_default.test &&
	grep "user3" hierarchy_default.test &&
	grep "user4" hierarchy_default.test
'

test_expect_success 'call view-bank on the root bank with --concise' '
	flux account view-bank -t -c root > hierarchy_concise_v1.test &&
	test_must_fail grep "user1" hierarchy_concise_v1.test &&
	test_must_fail grep "user2" hierarchy_concise_v1.test &&
	test_must_fail grep "user3" hierarchy_concise_v1.test &&
	test_must_fail grep "user4" hierarchy_concise_v1.test
'

test_expect_success 'edit the job_usage column for two of the associations' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user1 100 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user4 50
'

test_expect_success 'call view-bank on the root bank with --concise' '
	flux account view-bank -t -c root > hierarchy_concise_v2.test &&
	grep "user1" hierarchy_concise_v2.test &&
	grep "user4" hierarchy_concise_v2.test &&
	test_must_fail grep "user2" hierarchy_concise_v2.test &&
	test_must_fail grep "user3" hierarchy_concise_v2.test
'

test_expect_success 'call view-bank on the root bank with --concise and --parsable' '
	flux account view-bank -t -P -c root > hierarchy_concise_parsable.test &&
	grep "user1" hierarchy_concise_v2.test &&
	grep "user4" hierarchy_concise_v2.test &&
	test_must_fail grep "user2" hierarchy_concise_v2.test &&
	test_must_fail grep "user3" hierarchy_concise_v2.test
'

test_expect_success 'call view-bank on the root bank with --concise and --users' '
	flux account view-bank --users -c A > hierarchy_concise_parsable.test &&
	cat hierarchy_concise_parsable.test &&
	grep "user1" hierarchy_concise_v2.test &&
	test_must_fail grep "user2" hierarchy_concise_v2.test
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
