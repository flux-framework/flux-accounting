#!/bin/bash

test_description='ensure jobs are still held in PRIORITY after reprioritization if plugin has no data'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'
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
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=A &&
	flux account add-user --username=user2 --userid=5002 --bank=A &&
	flux account add-user --username=user3 --userid=5003 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'submit jobs as three different users' '
	job1=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	job2=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	job3=$(flux python ${SUBMIT_AS} 5003 hostname)
'

test_expect_success 'check that the jobs successfully received their priority' '
	flux job wait-event -vt 5 $job1 priority &&
	flux job wait-event -vt 5 $job2 priority &&
	flux job wait-event -vt 5 $job3 priority
'

test_expect_success 'unload plugin' '
	flux jobtap remove mf_priority.so
'

test_expect_success 'reload multi-factor priority plugin' '
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'reprioritize jobs' '
	cat <<-EOF >reprioritize.py
	import flux

	flux.Flux().rpc("job-manager.mf_priority.reprioritize")
	EOF
	flux python reprioritize.py
'

test_expect_success 'make sure job 1 is still in PRIORITY state' '
	flux job wait-event -vt 10 $job1 depend &&
	flux job info $job1 eventlog > eventlog.out &&
	cat eventlog.out &&
	grep "depend" eventlog.out
'

test_expect_success 'make sure job 2 is still in PRIORITY state' '
	flux job wait-event -vt 10 $job2 depend &&
	flux job info $job2 eventlog > eventlog.out &&
	cat eventlog.out &&
	grep "depend" eventlog.out
'

test_expect_success 'make sure job 3 is still in PRIORITY state' '
	flux job wait-event -vt 10 $job3 depend &&
	flux job info $job3 eventlog > eventlog.out &&
	cat eventlog.out &&
	grep "depend" eventlog.out
'

test_expect_success 'cancel jobs' '
	flux job cancel $job1 &&
	flux job cancel $job2 &&
	flux job cancel $job3
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
