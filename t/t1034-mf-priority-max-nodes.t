#!/bin/bash

test_description='test tracking node counts for associations in the priority plugin'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 5 job -o,--config-path=$(pwd)/conf.d

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
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add a user to the DB' '
	flux account add-user \
		--username=user1 \
		--userid=5001 \
		--bank=A \
		--max-nodes=5
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a 1-node sleep job' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -f json $job1 priority
'

test_expect_success 'check that association is using 1 node' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_nodes == 1" <query.json
'

test_expect_success 'cancel job' '
	flux cancel $job1 &&
	flux job wait-event -vt 10 $job1 clean
'

test_expect_success 'check that association is using 0 nodes after job cleans up' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_nodes == 0" <query.json
'

test_expect_success 'submit multiple jobs that use multiple nodes' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N2 sleep 60) &&
	job2=$(flux python ${SUBMIT_AS} 5001 -N3 sleep 60) &&
	flux job wait-event -f json $job1 priority &&
	flux job wait-event -f json $job2 priority
'

test_expect_success 'check that association is using 5 nodes' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_nodes == 5" <query.json
'

test_expect_success 'cancel 1 job and check that cur_nodes == 3' '
	flux cancel $job1 &&
	flux job wait-event -vt 10 $job1 clean &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_nodes == 3" <query.json
'

test_expect_success 'cancel the other job and check that cur_nodes == 0' '
	flux cancel $job2 &&
	flux job wait-event -vt 10 $job2 clean &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[0].banks[0].cur_nodes == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
