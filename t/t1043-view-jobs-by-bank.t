#!/bin/bash

test_description='test viewing and filtering job records by bank'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root bankA 1 &&
	flux account add-bank --parent-bank=root bankB 1
'

test_expect_success 'add a user with a list of projects to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=bankA &&
	flux account add-user --username=user1 --userid=5001 --bank=bankB &&
	flux account add-user --username=user2 --userid=5002 --bank=bankB
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit 2 jobs under bank A' '
	job1=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	flux job wait-event -f json ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	flux job wait-event -f json ${job2} priority &&
	flux cancel ${job1} &&
	flux cancel ${job2} &&
	flux job wait-event -vt 3 ${job1} clean &&
	flux job wait-event -vt 3 ${job2} clean
'

test_expect_success 'submit 2 jobs under bank B' '
	job1=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	flux job wait-event -f json ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	flux job wait-event -f json ${job2} priority &&
	flux cancel ${job1} &&
	flux cancel ${job2} &&
	flux job wait-event -vt 3 ${job1} clean &&
	flux job wait-event -vt 3 ${job2} clean
'

test_expect_success 'submit jobs under a secondary bank' '
	job1=$(flux python ${SUBMIT_AS} 5001 --setattr=system.bank=bankB hostname) &&
	flux job wait-event -f json ${job1} priority &&
	flux cancel ${job1} &&
	flux job wait-event -vt 3 ${job1} clean
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'look at all jobs (will show 5 records in total)' '
	flux account view-job-records -o "{username:<8} | {bank:<8}" > all_jobs.test &&
	cat <<-EOF >all_jobs.expected &&
	username | bank
	5001     | bankB
	5002     | bankB
	5002     | bankB
	5001     | bankA
	5001     | bankA
	EOF
	grep -f all_jobs.expected all_jobs.test
'

test_expect_success 'filter jobs by bankA (will show 2 records in total)' '
	flux account view-job-records \
		--bank=bankA \
		-o "{username:<8} | {bank:<8}" > bankA_jobs.test &&
	cat <<-EOF >bankA_jobs.expected &&
	username | bank
	5001     | bankA
	5001     | bankA
	EOF
	grep -f bankA_jobs.expected bankA_jobs.test
'

test_expect_success 'filter jobs by bankB (will show 3 records in total)' '
	flux account view-job-records \
		--bank=bankB \
		-o "{username:<8} | {bank:<8}" > bankB_jobs.test &&
	cat <<-EOF >bankB_jobs.expected &&
	username | bank
	5001     | bankB
	5002     | bankB
	5002     | bankB
	EOF
	grep -f bankB_jobs.expected bankB_jobs.test
'

test_expect_success 'filter jobs by bankB with short option' '
	flux account view-job-records \
		-B bankB \
		-o "{username:<8} | {bank:<8}" > bankB_jobs2.test &&
	cat <<-EOF >bankB_jobs2.expected &&
	username | bank
	5001     | bankB
	5002     | bankB
	5002     | bankB
	EOF
	grep -f bankB_jobs2.expected bankB_jobs2.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
