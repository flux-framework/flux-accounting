#!/bin/bash

test_description='test removing old job records from the flux-accounting database'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"
INSERT_JOBS="flux python ${SHARNESS_TEST_SRCDIR}/scripts/insert_jobs.py"

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

# get job records from jobs table
# arg1 - database path
get_job_records() {
		local dbpath=$1
		local i=0
		local row_count=0
		query="select count(*) from jobs;"

		row_count=$(${QUERYCMD} -t 100 ${dbpath} "${query}" | awk -F' = ' '{print $2}')
		echo $row_count
}

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

# insert_jobs.py inserts three fake job records into the jobs table in the
# flux-accounting database. Four total job records are added to the jobs table:
#
# Two of the jobs have a simulated time of finishing just over two weeks ago.
# One of the jobs has a simulated time of finishing very recently.
# One of the jobs has a simulated time of finishing over six months ago.
test_expect_success 'populate DB with four job records' '
	${INSERT_JOBS} ${DB_PATH}
'

test_expect_success 'ensure the jobs table has four records in it' '
	get_job_records ${DB_PATH} > result.out &&
	test $(cat result.out) -eq 4
'

test_expect_success 'do not pass an argument to scrub-old-jobs (should remove the oldest job)' '
	flux account -p ${DB_PATH} scrub-old-jobs &&
	get_job_records ${DB_PATH} > result.out &&
	test $(cat result.out) -eq 3
'

# Passing 0 for num_weeks is saying "Remove all records older than 0 weeks
# old," or rather, remove all jobs in the table.
test_expect_success 'if we pass 0 for num_weeks, all jobs will be removed' '
	flux account scrub-old-jobs 0 &&
	get_job_records ${DB_PATH} > result.out &&
	test $(cat result.out) -eq 0
'

# If num_weeks == 2, all jobs that have finished more than 2 weeks ago will be
# removed. In our testsuite, that should leave just the job that finished
# "recently".
test_expect_success 'only remove job records older than 2 weeks old' '
	${INSERT_JOBS} ${DB_PATH} &&
	flux account scrub-old-jobs 2 &&
	get_job_records ${DB_PATH} > result.out &&
	test $(cat result.out) -eq 1
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
