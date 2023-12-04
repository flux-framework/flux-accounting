#!/bin/bash

test_description='Test submitting jobs to queues after queue access is changed'

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
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user1001 --userid=1001 --bank=A &&
	flux account add-user --username=user1002 --userid=1001 --bank=A
'

test_expect_success 'submit a job with no user/bank info loaded to plugin' '
	jobid1=$(flux python ${SUBMIT_AS} 1001 --wait-event=depend sleep 60)
'

test_expect_success 'make sure job is held in state PRIORITY' '
	test $(flux jobs -no {state} ${jobid1}) = PRIORITY
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'check that held job transitions to RUN' '
	test $(flux jobs -no {state} ${jobid1}) = RUN
'

test_expect_success 'cancel job' '
	flux job cancel $jobid1
'

test_expect_success 'submit a job to plugin while not having an entry in the plugin' '
	test_must_fail flux python ${SUBMIT_AS} 1003 hostname > no_user_entry.out 2>&1 &&
	grep "cannot find user/bank or user/default bank entry for:" no_user_entry.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
