#!/bin/bash

test_description='test handling pending jobs sent back to PRIORITY after aux items cleared'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

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
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'stop scheduler from allocating resources to jobs' '
	flux queue stop
'

test_expect_success 'submit job and make sure it is pending' '
	job=$(flux python ${SUBMIT_AS} 5001 sleep 60) &&
	flux job wait-event -vt 5 ${job} priority
'

# unloading the jobtap plugin will clear all of the aux items set on the job
test_expect_success 'unload and reload mf_priority.so (clears aux items on job)' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'job remains to be held in SCHED' '
	test $(flux jobs -no {state} ${job}) = "SCHED"
'

test_expect_success 'start queue so that resources can be allocated to job' '
	flux queue start
'

test_expect_success 'update the plugin with flux-accounting information' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'job proceeds to RUN' '
	flux job wait-event -vt 5 ${job} alloc
'

test_expect_success 'cancel job' '
	flux cancel ${job}
'

test_done
