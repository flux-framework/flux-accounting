#!/bin/bash

test_description='test viewing duration_delta fields with view-job-records'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

# update job records with actual_duration
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

# Submit a number of jobs with the same requested duration.
test_expect_success 'submit job with duration of 60 seconds' '
	job1=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
	flux job wait-event -vt 3 ${job1} alloc
'

test_expect_success 'submit job with duration of 60 seconds' '
	job2=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
	flux job wait-event -vt 3 ${job2} alloc
'

test_expect_success 'submit job with duration of 60 seconds' '
	job3=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
	flux job wait-event -vt 3 ${job3} alloc
'

test_expect_success 'submit job with duration of 60 seconds' '
	job4=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
	flux job wait-event -vt 3 ${job4} alloc
'

test_expect_success 'submit job with duration of 60 seconds' '
	job5=$(flux python ${SUBMIT_AS} 50001 -S duration=60 hostname) &&
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

# Edit the actual duration of the jobs that ran just above for test purposes
# without actually having to run those jobs for a certain duration
test_expect_success 'edit actual duration of test jobs' '
	job1=$(flux job id -t dec ${job1}) &&
	job2=$(flux job id -t dec ${job2}) &&
	job3=$(flux job id -t dec ${job3}) &&
	job4=$(flux job id -t dec ${job4}) &&
	job5=$(flux job id -t dec ${job5}) &&
	update_actual_duration ${DB_PATH} 5 ${job1} &&
	update_actual_duration ${DB_PATH} 5 ${job2} &&
	update_actual_duration ${DB_PATH} 20 ${job3} &&
	update_actual_duration ${DB_PATH} 30 ${job4} &&
	update_actual_duration ${DB_PATH} 59 ${job5}
'

test_expect_success 'view jobs with duration_delta' '
	flux account view-job-records \
		-o "{jobid:<20} | {duration_delta:<18}" > duration_delta.out &&
	grep ${job1} duration_delta.out | grep "55.0" &&
	grep ${job2} duration_delta.out | grep "55.0"  &&
	grep ${job3} duration_delta.out | grep "40.0"  &&
	grep ${job4} duration_delta.out | grep "30.0"  &&
	grep ${job5} duration_delta.out | grep "1.0"
'

test_expect_success 'filter for jobs with a duration_delta < 10 seconds' '
	flux account view-job-records \
		-D "< 10" -o "{jobid:<20}" > delta_lt_10_seconds.out &&
	test_must_fail grep ${job1} delta_lt_10_seconds.out &&
	test_must_fail grep ${job2} delta_lt_10_seconds.out &&
	test_must_fail grep ${job3} delta_lt_10_seconds.out &&
	test_must_fail grep ${job4} delta_lt_10_seconds.out &&
	grep ${job5} delta_lt_10_seconds.out
'

test_expect_success 'filter for jobs with a duration_delta >= 1 second' '
	flux account view-job-records \
		-D ">= 1" -o "{jobid:<20}" > delta_ge_1_seconds.out &&
	grep ${job1} delta_ge_1_seconds.out &&
	grep ${job2} delta_ge_1_seconds.out &&
	grep ${job3} delta_ge_1_seconds.out &&
	grep ${job4} delta_ge_1_seconds.out &&
	grep ${job5} delta_ge_1_seconds.out
'

test_expect_success 'filter for jobs with a duration_delta > 10 and < 55 seconds' '
	flux account view-job-records \
		-D "> 10" "< 55" -o "{jobid:<20}" > delta_multiple_filters.out &&
	test_must_fail grep ${job1} delta_multiple_filters.out &&
	test_must_fail grep ${job2} delta_multiple_filters.out &&
	grep ${job3} delta_multiple_filters.out &&
	grep ${job4} delta_multiple_filters.out &&
	test_must_fail grep ${job5} delta_multiple_filters.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
