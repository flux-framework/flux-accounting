#!/bin/bash

test_description='Test getting internal state of plugin using flux jobtap query'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/plugin_state

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

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success HAVE_JQ 'flux jobtap query returns basic information' '
	flux jobtap query mf_priority.so >query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".name == \"mf_priority.so\"" <query.json &&
	jq -e ".path == \"${MULTI_FACTOR_PRIORITY}\"" <query.json
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root account1 1 &&
	flux account add-bank --parent-bank=root account2 1 &&
	flux account add-bank --parent-bank=root account3 1
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze --priority=100 &&
	flux account add-queue silver --priority=200 &&
	flux account add-queue gold --priority=300
'

test_expect_success 'add a user with two different banks to the DB' '
	flux account add-user --username=user1001 --userid=1001 --bank=account1 --max-running-jobs=2 &&
	flux account add-user --username=user1001 --userid=1001 --bank=account2
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success HAVE_JQ 'fetch plugin state' '
	flux jobtap query mf_priority.so > query_1.json &&
	jq ".mf_priority_map" query_1.json > internal_state_1.test &&
	test_cmp ${EXPECTED_FILES}/internal_state_1.expected internal_state_1.test
'

test_expect_success 'submit max number of jobs under default bank (1 held job due to max_run_jobs limit)' '
	jobid1=$(flux python ${SUBMIT_AS} 1001 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 1001 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 1001 sleep 60)
'

test_expect_success HAVE_JQ 'fetch plugin state and make sure that jobs are reflected in JSON object' '
	flux jobtap query mf_priority.so > query_2.json &&
	test_debug "jq -S . <query_2.json" &&
	jq -e ".mf_priority_map[0].banks[0].held_jobs | length == 1" <query_2.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_run_jobs == 2" <query_2.json &&
	jq -e ".mf_priority_map[0].banks[0].cur_active_jobs == 3" <query_2.json
'

test_expect_success 'cancel jobs' '
	flux job cancel $jobid1 &&
	flux job cancel $jobid2 &&
	flux job cancel $jobid3
'

test_expect_success 'add another user to flux-accounting DB and send it to plugin' '
	flux account add-user --username=user1002 --userid=1002 --bank=account3 --queues="bronze" &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success HAVE_JQ 'fetch plugin state again with multiple users' '
	flux jobtap query mf_priority.so > query_3.json &&
	jq ".mf_priority_map" query_3.json > internal_state_3.test &&
	test_cmp ${EXPECTED_FILES}/internal_state_3.expected internal_state_3.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
