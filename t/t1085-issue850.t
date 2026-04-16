#!/bin/bash

test_description='call view-usage-report after submitting jobs to plugin'

. $(dirname $0)/sharness.sh

QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

export FLUX_CONF_DIR=$(pwd)
test_under_flux 4 job -Slog-stderr-level=1

# select job records from flux-accounting DB
select_job_records() {
		local dbpath=$1
		query="SELECT * FROM jobs;"
		${QUERYCMD} -t 100 ${dbpath} "${query}"
}

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'run fetch-job-records script with no jobs in jobs_table' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=$(whoami) --userid=$(id -u) --bank=A
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit some jobs and wait for them to finish running' '
	jobid1=$(flux submit -N 1 sleep 1) &&
	jobid2=$(flux submit -N 1 sleep 1) &&
	flux job wait-event -vt 3 ${jobid1} clean &&
	flux job wait-event -vt 3 ${jobid2} clean
'

test_expect_success 'fetch-job-records puts completed jobs in jobs table' '
    flux account-fetch-job-records -p ${DB_PATH} &&
	select_job_records ${DB_PATH} > records.out &&
	grep "sleep" records.out
'

test_expect_success 'view-usage-report works' '
	flux account view-usage-report -s 12/01/2024 -u $(whoami)
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
