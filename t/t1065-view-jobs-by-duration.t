#!/bin/bash

test_description='test viewing duration fields with view-job-records'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

# update job records with actual duration
update_actual_duration() {
		local dbpath=$1
		query="UPDATE jobs SET actual_duration='$2' WHERE id=$3"
		${QUERYCMD} -t 100 ${dbpath} "${query}"
}

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

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

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association' '
	flux account add-user --username=user1 --userid=50001 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

# Submit a number of jobs with different requested durations.
test_expect_success 'submit job with duration of 60 seconds' '
	job1=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
	flux job wait-event -vt 3 ${job1} alloc
'

test_expect_success 'submit job with duration of 120 seconds' '
	job2=$(flux python ${SUBMIT_AS} 50001 -S duration=120 hostname) &&
	flux job wait-event -vt 3 ${job2} alloc
'

test_expect_success 'submit job with duration of 240 seconds' '
	job3=$(flux python ${SUBMIT_AS} 50001 -S duration=240 hostname) &&
	flux job wait-event -vt 3 ${job3} alloc
'

test_expect_success 'submit job with duration of 1800 seconds' '
	job4=$(flux python ${SUBMIT_AS} 50001 -S duration=1800 hostname) &&
	flux job wait-event -vt 3 ${job4} alloc
'

test_expect_success 'submit job with duration of 3600 seconds' '
	job5=$(flux python ${SUBMIT_AS} 50001 -S duration=3600 hostname) &&
	flux job wait-event -vt 3 ${job5} alloc
'

test_expect_success 'cancel all jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2} &&
	flux cancel ${job3} &&
	flux cancel ${job4} &&
	flux cancel ${job5} &&
	flux job wait-event -vt 3 ${job1} clean &&
	flux job wait-event -vt 3 ${job2} clean &&
	flux job wait-event -vt 3 ${job3} clean &&
	flux job wait-event -vt 3 ${job4} clean &&
	flux job wait-event -vt 3 ${job5} clean
'

test_expect_success 'fetch jobs and insert them into flux-accounting DB' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'filtering jobs with a bad expression raises a ValueError' '
	test_must_fail flux account view-job-records -d "foo 60" > bad_expr_1.err 2>&1 &&
	grep "expression must start with <, <=, =, >=, or >" bad_expr_1.err
'

test_expect_success 'filtering jobs with a bad expression raises a ValueError' '
	test_must_fail flux account view-job-records -d "< 60 120" > bad_expr_2.err 2>&1 &&
	grep "expression expects one operator and one value" bad_expr_2.err
'

test_expect_success 'filtering jobs with a bad expression raises a ValueError' '
	test_must_fail flux account view-job-records -d "< foo" > bad_expr_3.err 2>&1 &&
	grep "expression expects to be compared with a number" bad_expr_3.err
'

test_expect_success 'trying to filter jobs with a SQL injection raises ValueError' '
	test_must_fail flux account view-job-records \
		-d "<60;DROP\nTABLE\n\IF\nEXISTS\njobs;< 50" > bad_expr_4.err 2>&1 &&
	grep "expression must start with <, <=, =, >=, or >" bad_expr_4.err
'

test_expect_success 'filter jobs with a duration less than 100 seconds' '
	flux account view-job-records -d "< 100" > filtered_jobs_lt.out &&
	test $(grep -c "A" filtered_jobs_lt.out) -eq 1
'

test_expect_success 'filter jobs with a duration less than or equal to 120 seconds' '
	flux account view-job-records -d "<= 120" > filtered_jobs_le.out &&
	test $(grep -c "A" filtered_jobs_le.out) -eq 2
'

test_expect_success 'filter jobs with a duration equal to 1800 seconds' '
	flux account view-job-records -d "= 1800" > filtered_jobs_eq.out &&
	test $(grep -c "A" filtered_jobs_eq.out) -eq 1
'

test_expect_success 'filter jobs with a duration greater than or equal to 1 second' '
	flux account view-job-records -d ">= 1" > filtered_jobs_eq.out &&
	test $(grep -c "A" filtered_jobs_eq.out) -eq 5
'

test_expect_success 'filter jobs with a duration greater than 3600 seconds' '
	flux account view-job-records -d "> 3600" > filtered_jobs_eq.out &&
	test $(grep -c "A" filtered_jobs_eq.out) -eq 0
'

test_expect_success 'filter jobs with multiple expressions' '
	flux account view-job-records -d "> 1" "< 121" > filtered_jobs_multiple.out &&
	test $(grep -c "A" filtered_jobs_multiple.out) -eq 2
'

# Edit the actual duration of the jobs that ran just above for test purposes
# without actually having to run those jobs for a certain duration.
test_expect_success 'edit actual duration of test jobs' '
	job3=$(flux job id -t dec ${job3}) &&
	job4=$(flux job id -t dec ${job4}) &&
	job5=$(flux job id -t dec ${job5}) &&
	update_actual_duration ${DB_PATH} 120 ${job3} &&
	update_actual_duration ${DB_PATH} 1800 ${job4} &&
	update_actual_duration ${DB_PATH} 2400 ${job5}
'

test_expect_success 'filter job records with an actual duration greater than 100 seconds' '
	flux account view-job-records -e "> 100" > filtered_jobs_gt100.out &&
	test $(grep -c "A" filtered_jobs_gt100.out) -eq 3
'

test_expect_success 'filter job records with an actual duration greater than 1800 seconds' '
	flux account view-job-records -e ">= 1800" > filtered_jobs_ge1800.out &&
	test $(grep -c "A" filtered_jobs_ge1800.out) -eq 2
'

test_expect_success 'filter job records with both requested and actual duration' '
	flux account view-job-records -d "= 3600" -e "> 1600" "< 2500" \
		> filtered_jobs_both_durations.out &&
	test $(grep -c "A" filtered_jobs_both_durations.out) -eq 1
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
