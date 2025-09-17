#!/bin/bash

test_description='test viewing and filtering job records by bank'

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
	flux cancel ${job2}
'

test_expect_success 'submit 2 jobs under bank B' '
	job1=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	flux job wait-event -f json ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	flux job wait-event -f json ${job2} priority &&
	flux cancel ${job1} &&
	flux cancel ${job2}
'

test_expect_success 'submit jobs under a secondary bank' '
	job1=$(flux python ${SUBMIT_AS} 5001 --setattr=system.bank=bankB hostname) &&
	flux job wait-event -f json ${job1} priority &&
	flux cancel ${job1}
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'look at all jobs (will show 5 records in total)' '
	flux account view-job-records > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2 &&
	test $(grep -c "bankB" all_jobs.out) -eq 3
'

test_expect_success 'filter jobs by bankA (will show 2 records in total)' '
	flux account view-job-records --bank=bankA > bankA_jobs.out &&
	test $(grep -c "5001" bankA_jobs.out) -eq 2 &&
	test $(grep -c "5002" bankA_jobs.out) -eq 0
'

test_expect_success 'filter jobs by bankB (will show 3 records in total)' '
	flux account view-job-records --bank=bankB > bankB_jobs.out &&
	test $(grep -c "5001" bankB_jobs.out) -eq 1 &&
	test $(grep -c "5002" bankB_jobs.out) -eq 2 
'

test_expect_success 'filter jobs by bankB with short option' '
	flux account view-job-records -B bankB > bankB_jobs.out &&
	test $(grep -c "5001" bankB_jobs.out) -eq 1 &&
	test $(grep -c "5002" bankB_jobs.out) -eq 2 
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
