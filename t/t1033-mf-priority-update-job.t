#!/bin/bash

test_description='test updating a combination of queue and bank for a pending job in priority plugin'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze --priority=100 &&
	flux account add-queue silver --priority=200 &&
	flux account add-queue gold --priority=300
'

test_expect_success 'add a user to the DB' '
	flux account add-user --username=user5001 \
		--userid=5001 \
		--bank=A \
		--queues="bronze,silver" &&
	flux account add-user --username=user5001 \
		--userid=5001 \
		--bank=B \
		--queues="bronze,silver"
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'configure flux with some queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload
'

test_expect_success 'submit job for testing' '
	jobid=$(flux python ${SUBMIT_AS} 5001 --queue=bronze sleep 30) &&
	flux job wait-event -f json $jobid priority &&
	flux job eventlog $jobid > eventlog.out &&
	grep "1050000" eventlog.out
'

test_expect_success 'update both queue and bank successfully' '
	flux update $jobid queue=silver bank=B &&
	flux job wait-event -f json $jobid priority &&
	flux job eventlog $jobid > eventlog.out &&
	grep "attributes.system.queue=\"silver\"" eventlog.out &&
	grep 2050000 eventlog.out &&
	grep "attributes.system.bank=\"B\"" eventlog.out &&
	flux job cancel $jobid
'

test_expect_success 'submit another job for testing' '
	jobid=$(flux python ${SUBMIT_AS} 5001 --queue=bronze sleep 30) &&
	flux job wait-event -f json $jobid priority
'

test_expect_success 'update job with invalid combination (invalid bank)' '
	test_must_fail flux update $jobid queue=silver bank=foo > nonexistent_bank.out 2>&1 &&
	test_debug "cat nonexistent_bank.out" &&
	grep "cannot find user/bank or user/default bank entry for uid:" nonexistent_bank.out
'

test_expect_success 'check that job is still in original queue' '
	flux job info $jobid jobspec > jobspec.out &&
	grep "\"queue\": \"bronze\"" jobspec.out
'

test_expect_success 'update job with invalud combination (invalid queue)' '
	test_must_fail flux update $jobid bank=B queue=gold > unavail_queue.out 2>&1 &&
	test_debug "cat unavail_queue.out" &&
	grep "ERROR: mf_priority: queue not valid for user: gold" unavail_queue.out
'

test_expect_success 'check that job is still under original bank' '
	flux job eventlog $jobid > eventlog.out &&
	grep "attributes.system.bank=\"A\"" eventlog.out &&
	flux job cancel $jobid
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
