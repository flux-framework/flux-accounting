#!/bin/bash

test_description='Test comparing job counts when submitting jobs that take up all resources'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/plugin_state

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
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root account1 1 &&
	flux account add-bank --parent-bank=root account2 1 &&
	flux account add-bank --parent-bank=root account3 1
'

test_expect_success 'add a user with two different banks to the DB' '
	flux account add-user --username=user1001 --userid=1001 --bank=account1 --max-running-jobs=5 --max-active-jobs=10 &&
	flux account add-user --username=user1001 --userid=1001 --bank=account2
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a sleep 180 job and ensure it is running' '
	jobid1=$(flux python ${SUBMIT_AS} 1001 sleep 180) &&
	flux job wait-event -vt 60 ${jobid1} alloc
'

test_expect_success 'stop scheduler from allocating resources to jobs' '
	flux queue stop
'

test_expect_success 'submit 2 more sleep 180 jobs; ensure both are in SCHED state' '
	jobid2=$(flux python ${SUBMIT_AS} 1001 sleep 180) &&
	jobid3=$(flux python ${SUBMIT_AS} 1001 sleep 180) &&
	flux job wait-event -vt 60 ${jobid2} priority &&
	flux job wait-event -vt 60 ${jobid3} priority
'

test_expect_success 'ensure current running and active jobs are correct: 1 running, 3 active' '
	flux jobtap query mf_priority.so > query_1.json &&
	test_debug "jq -S . <query_1.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 1" <query_1.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 3" <query_1.json
'

test_expect_success 'update the plugin and ensure current running and active jobs are correct' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db &&
	flux jobtap query mf_priority.so > query_2.json &&
	test_debug "jq -S . <query_2.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 1" <query_2.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 3" <query_2.json
'

test_expect_success 'change the priority of one of the jobs' '
	flux job urgency ${jobid2} 31 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db &&
	flux job eventlog ${jobid2} | grep ^priority | tail -n 1 | priority=4294967295
'

test_expect_success 'ensure job counts are still the same: 1 running, 3 active' '
	flux jobtap query mf_priority.so > query_3.json &&
	test_debug "jq -S . <query_3.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 1" <query_3.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 3" <query_3.json
'

test_expect_success 'cancel one of the scheduled jobs, check job counts are correct: 1 running, 2 active' '
	flux cancel ${jobid2} &&
	flux jobtap query mf_priority.so > query_4.json &&
	test_debug "jq -S . <query_4.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 1" <query_4.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 2" <query_4.json
'

test_expect_success 'cancel sleep 180 job(s), check job counts: 0 running, 0 active' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid3} &&
	flux jobtap query mf_priority.so > query_5.json &&
	test_debug "jq -S . <query_5.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 0" <query_5.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 0" <query_5.json
'

test_done
