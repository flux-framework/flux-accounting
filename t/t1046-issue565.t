#!/bin/bash

test_description='test viewing and filtering jobs with different timestamp formats'

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
	flux account add-bank --parent-bank=root bankA 1
'

test_expect_success 'add a user to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=bankA
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit 2 jobs under bank A' '
	job1=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	flux job wait-event -f json $job1 priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	flux job wait-event -f json $job2 priority &&
	flux cancel $job1 &&
	flux cancel $job2
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

# Pass different formatted timestamps to view *all* of the jobs in the archive.
test_expect_success 'after-start-time: seconds-since-epoch timestamp (01/01/1970)' '
	flux account view-job-records --after-start-time=0 > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'after-start-time: human-readable timestamp (M/D/YYYY)' '
	flux account view-job-records --after-start-time="1/1/1970" > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'after-start-time: human-readable timestamp (YYYY-MM-DD HH:MM:SS)' '
	flux account view-job-records --after-start-time="1970-01-01 08:00:00" > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'after-start-time: human-readable timestamp (Month Day, Year Time)' '
	flux account view-job-records --after-start-time="Jan 01, 1970 8am" > all_jobs.out &&
	cat all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'before-end-time: seconds-since-epoch timestamp (01/01/3025)' '
	flux account view-job-records --before-end-time=33292663664 > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'before-end-time: human-readable timestamp (M/D/YYYY)' '
	flux account view-job-records --before-end-time="1/1/3025" > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'before-end-time: human-readable timestamp (YYYY-MM-DD HH:MM:SS)' '
	flux account view-job-records --before-end-time="3025-01-01 08:00:00" > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

test_expect_success 'before-end-time: human-readable timestamp (Month Day, Year Time)' '
	flux account view-job-records --before-end-time="Jan 01, 3025 8am" > all_jobs.out &&
	test $(grep -c "bankA" all_jobs.out) -eq 2
'

# Pass different formatted timestamps to view *none* of the jobs in the archive.
test_expect_success 'after-start-time: human-readable timestamp (M/D/YYYY)' '
	flux account view-job-records --after-start-time="1/1/3025" > no_jobs.out &&
	test $(grep -c "bankA" no_jobs.out) -eq 0
'

test_expect_success 'before-end-time: human-readable timestamp (M/D/YYYY)' '
	flux account view-job-records --before-end-time="1/1/1970" > no_jobs.out &&
	test $(grep -c "bankA" no_jobs.out) -eq 0
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
