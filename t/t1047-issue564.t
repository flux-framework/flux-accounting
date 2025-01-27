#!/bin/bash

test_description='test viewing jobs with different ID formats'

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

test_expect_success 'add a user with a list of projects to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=bankA
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job' '
	job1=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	flux job wait-event -f json $job1 priority &&
	flux cancel $job1
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'call view-job-records with f58 job ID' '
	flux account view-job-records --jobid ${job1} > f58_id.out &&
	test $(grep -c "bankA" f58_id.out) -eq 1
'

test_expect_success 'call view-job-records with hex job ID' '
	job1_hex=$(flux job id -t hex ${job1}) &&
	flux account view-job-records --jobid ${job1_hex} > hex_id.out &&
	test $(grep -c "bankA" hex_id.out) -eq 1
'

test_expect_success 'call view-job-records with kvs job ID' '
	job1_kvs=$(flux job id -t kvs ${job1}) &&
	flux account view-job-records --jobid ${job1_kvs} > kvs_id.out &&
	test $(grep -c "bankA" kvs_id.out) -eq 1
'

test_expect_success 'call view-job-records with dothex job ID' '
	job1_dothex=$(flux job id -t dothex ${job1}) &&
	flux account view-job-records --jobid ${job1_dothex} > dothex_id.out &&
	test $(grep -c "bankA" dothex_id.out) -eq 1
'

test_expect_success 'call view-job-records with words job ID' '
	job1_words=$(flux job id -t words ${job1}) &&
	flux account view-job-records --jobid ${job1_words} > words_id.out &&
	test $(grep -c "bankA" words_id.out) -eq 1
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
