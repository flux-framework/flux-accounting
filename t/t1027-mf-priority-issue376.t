#!/bin/bash

test_description='test updating attributes of a job with flux-accounting limits imposed'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

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

test_expect_success 'add a user to the DB' '
	flux account add-user --username=user5001 \
		--userid=5001 \
		--bank=A \
		--max-active-jobs=2
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit job for testing' '
	jobid1=$(flux python ${SUBMIT_AS} 5001 --urgency=0 sleep 30) &&
	jobid2=$(flux python ${SUBMIT_AS} 5001 --urgency=0 sleep 30)
'

test_expect_success 'update of duration of pending job works while at active jobs limit' '
	flux update ${jobid1} duration=1m &&
	flux job wait-event -vt 10 ${jobid1} priority &&
	flux job eventlog ${jobid1} \
		| grep jobspec-update \
		| grep duration=60
'

test_expect_success 'active jobs limit of user/bank remains the same after job-update' '
	flux jobtap query mf_priority.so > job_limits.json &&
	test_debug "jq -S . <job_limits.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_active_jobs == 2" <job_limits.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].max_active_jobs == 2" <job_limits.json
'

test_expect_success 'third submitted job will be rejected because of active jobs limit' '
	test_must_fail flux python ${SUBMIT_AS} 5001 sleep 60 > max_active_jobs.out 2>&1 &&
	test_debug "cat max_active_jobs.out" &&
	grep "user has max active jobs" max_active_jobs.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
