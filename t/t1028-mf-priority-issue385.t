#!/bin/bash

test_description='Test submitting jobs to queues after queue access is changed'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB, start flux-accounting service' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db &&
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit a job with no user/bank info loaded to plugin' '
	jobid1=$(flux python ${SUBMIT_AS} 5001 --wait-event=depend hostname) &&
	test $(flux jobs -no {state} ${jobid1}) = PRIORITY
'

test_expect_success 'submit a job as another user, check that it is also in state PRIORITY' '
	jobid2=$(flux python ${SUBMIT_AS} 5002 --wait-event=depend hostname) &&
	test $(flux jobs -no {state} ${jobid2}) = PRIORITY
'

test_expect_success 'add banks, users to flux-accounting DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=5001 --bank=A &&
	flux account add-user --username=user2 --userid=5002 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'check that jobs transition to RUN' '
	test $(flux jobs -no {state} ${jobid1}) = RUN &&
	test $(flux jobs -no {state} ${jobid2}) = RUN
'

test_expect_success 'submitting a job under invalid user while plugin has data fails' '
	test_must_fail flux python ${SUBMIT_AS} 9999 hostname > invalid_user.out 2>&1 &&
	test_debug "cat invalid_user.out" &&
	grep "cannot find user/bank or user/default bank entry for: 9999" invalid_user.out
'

test_expect_success 'cancel running jobs' '
	flux job cancel $jobid1 &&
	flux job cancel $jobid2
'

test_expect_success 'add the previously invalid user to flux-accounting DB, plugin' '
	flux account add-user --username=user9999 --userid=9999 --bank=A &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'previously invalid user can now submit jobs' '
	jobid3=$(flux python ${SUBMIT_AS} 9999 hostname) &&
	test $(flux jobs -no {state} ${jobid3}) = RUN &&
	flux job cancel $jobid3
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_done
