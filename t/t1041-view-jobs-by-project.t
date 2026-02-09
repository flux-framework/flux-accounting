#!/bin/bash

test_description='test viewing and filtering job records by project'

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
	flux account add-bank --parent-bank=root account1 1
'

test_expect_success 'add projects to the DB' '
	flux account add-project projectA &&
	flux account add-project projectB
'

test_expect_success 'add a user with a list of projects to the DB' '
	flux account add-user \
		--username=user1 \
		--userid=5001 \
		--bank=account1 \
		--projects="projectA,projectB"
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit 2 jobs under projectA' '
	job1=$(flux python ${SUBMIT_AS} 5001 --setattr=system.project=projectA hostname) &&
	flux job wait-event -f json $job1 priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 --setattr=system.project=projectA hostname) &&
	flux job wait-event -f json $job2 priority &&
	flux cancel $job1 &&
	flux cancel $job2
'

test_expect_success 'submit 2 jobs under projectB' '
	job1=$(flux python ${SUBMIT_AS} 5001 --setattr=system.project=projectB hostname) &&
	flux job wait-event -f json $job1 priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 --setattr=system.project=projectB hostname) &&
	flux job wait-event -f json $job2 priority &&
	flux cancel $job1 &&
	flux cancel $job2
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'look at all jobs (will show 4 records)' '
	flux account view-job-records > all_jobs.out &&
	test $(grep -c "projectA" all_jobs.out) -eq 2 &&
	test $(grep -c "projectB" all_jobs.out) -eq 2
'

test_expect_success 'filter jobs by projectA (will show 2 records)' '
	flux account view-job-records --project=projectA > projectA_jobs.out &&
	test $(grep -c "projectA" projectA_jobs.out) -eq 2
'

test_expect_success 'filter jobs by projectB (will show 2 records)' '
	flux account view-job-records --project=projectB > projectB_jobs.out &&
	test $(grep -c "projectB" projectB_jobs.out) -eq 2
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
