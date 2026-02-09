#!/bin/bash

test_description='test updating the bank for a pending job in priority plugin'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

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
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'add a user to the DB' '
	flux account add-user \
		--username=user1 \
		--userid=5001 \
		--bank=A &&
	flux account add-user \
		--username=user1 \
		--userid=5001 \
		--bank=B \
		--max-active-jobs=3 \
		--max-running-jobs=2
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit one job under default bank, two under non-default bank' '
	job1=$(flux python ${SUBMIT_AS} 5001 --urgency=0 sleep 30) &&
	job2=$(flux python ${SUBMIT_AS} 5001 --setattr=bank=B --urgency=0 sleep 30) &&
	job3=$(flux python ${SUBMIT_AS} 5001 --setattr=bank=B --urgency=0 sleep 30)
'

test_expect_success 'update of bank of pending job works' '
	flux update ${job1} bank=B &&
	flux job wait-event -t 30 ${job1} priority &&
	flux job eventlog ${job1} > eventlog.out &&
	grep "attributes.system.bank=\"B\"" eventlog.out
'

test_expect_success 'trying to update to a bank user does not have access to fails in job.validate' '
	test_must_fail flux update ${job1} bank=C > invalid_bank.out 2>&1 &&
	test_debug "cat invalid_bank.out" &&
	grep "cannot find flux-accounting entry for uid/bank: 5001/C" invalid_bank.out
'

test_expect_success 'trying to update to a bank that does not exist fails in job.validate' '
	test_must_fail flux update ${job1} bank=foo > nonexistent_bank.out 2>&1 &&
	test_debug "cat nonexistent_bank.out" &&
	grep "cannot find flux-accounting entry for uid/bank: 5001/foo" nonexistent_bank.out
'

test_expect_success 'update a job to another bank that is at max-active-jobs limit' '
	job4=$(flux python ${SUBMIT_AS} 5001 --urgency=0 sleep 30) &&
	test_must_fail flux update ${job4} bank=B > max_active_jobs.out 2>&1 &&
	test_debug "cat max_active_jobs.out" &&
	grep "new bank is already at max-active-jobs limit" max_active_jobs.out &&
	flux cancel ${job4}
'

test_expect_success 'cancel one of the jobs so bank is not at max-active-jobs limit' '
	flux cancel ${job3}
'

test_expect_success 'update urgency of held jobs so they transition to RUN' '
	flux job urgency ${job1} default &&
	flux job urgency ${job2} default &&
	flux job wait-event -t 10 ${job1} alloc &&
	flux job wait-event -t 10 ${job2} alloc
'

test_expect_success 'update a job to another bank that is at max-run-jobs limit' '
	job5=$(flux python ${SUBMIT_AS} 5001 --urgency=0 sleep 30) &&
	test_must_fail flux update ${job5} bank=B > max_run_jobs.out 2>&1 &&
	test_debug "cat max_run_jobs.out" &&
	grep "already at max-run-jobs limit is not allowed" max_run_jobs.out &&
	flux cancel ${job5}
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2}
'

test_expect_success 'submit job under non-default bank' '
	job6=$(flux python ${SUBMIT_AS} 5001 --setattr=bank=B --urgency=0 sleep 30)
'

test_expect_success 'updating job to default bank works' '
	flux update ${job6} bank=A &&
	flux job wait-event -t 30 ${job6} priority &&
	flux job eventlog ${job6} > eventlog.out &&
	grep "attributes.system.bank=\"A\"" eventlog.out
'

test_expect_success 'check that plugin also sees the job update' '
	flux jobtap query mf_priority.so > query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].bank_name == \"A\"" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_active_jobs == 1" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[1].bank_name == \"B\"" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[1].cur_active_jobs == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
