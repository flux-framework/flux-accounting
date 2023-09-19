#!/bin/bash

test_description='test adding default bank to jobspec in multi-factor priority plugin'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account1 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account2 1
'

test_expect_success 'add a user to the DB' '
	flux account -p ${DB_PATH} add-user --username=user1001 --userid=1001 --bank=account1 &&
	flux account -p ${DB_PATH} add-user --username=user1001 --userid=1001 --bank=account2
'

test_expect_success 'submit a job before plugin has any flux-accounting information' '
	jobid=$(flux python ${SUBMIT_AS} 1002 hostname) &&
	flux job wait-event -vt 60 $jobid depend &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "depend" eventlog.out
'

test_expect_success 'add user to flux-accounting DB and update plugin' '
	flux account -p ${DB_PATH} add-user --username=user1002 --userid=1002 --bank=account1 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'check that bank was added to jobspec' '
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "{\"attributes.system.bank\":\"account1\"}" eventlog.out &&
	flux job cancel $jobid
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'successfully submit a job under a specified bank' '
	jobid=$(flux python ${SUBMIT_AS} 1001 --setattr=system.bank=account2 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid jobspec > jobspec.out &&
	grep "account2" jobspec.out &&
	flux job cancel $jobid
'

test_expect_success 'successfully submit a job under a default bank' '
	jobid=$(flux python ${SUBMIT_AS} 1001 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "{\"attributes.system.bank\":\"account1\"}" eventlog.out &&
	flux job cancel $jobid
'

test_expect_success 'update the default bank for the user' '
	flux account -p ${DB_PATH} edit-user user1001 --default-bank=account2 &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'successfully submit a job under the new default bank' '
	jobid=$(flux python ${SUBMIT_AS} 1001 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "{\"attributes.system.bank\":\"account2\"}" eventlog.out &&
	flux job cancel $jobid
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
