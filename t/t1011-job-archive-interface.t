#!/bin/bash

test_description='test fetching jobs and updating the fair share values for a group of users'

. $(dirname $0)/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
ARCHIVEDIR=`pwd`
ARCHIVEDB="${ARCHIVEDIR}/jobarchive.db"
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"
NO_JOBS=${SHARNESS_TEST_SRCDIR}/expected/job_usage/no_jobs.expected

export FLUX_CONF_DIR=$(pwd)
test_under_flux 4 job

flux setattr log-stderr-level 1

# wait for job to be stored in job archive
# arg1 - jobid
# arg2 - database path
wait_db() {
		local jobid=$(flux job id $1)
		local dbpath=$2
		local i=0
		query="select id from jobs;"
		while ! ${QUERYCMD} -t 100 ${dbpath} "${query}" | grep $jobid > /dev/null \
			   && [ $i -lt 50 ]
		do
				sleep 0.1
				i=$((i + 1))
		done
		if [ "$i" -eq "100" ]
		then
			return 1
		fi
		return 0
}

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
	flux account add-bank --parent-bank=root account1 1 &&
	flux account add-bank --parent-bank=root account2 1
'

test_expect_success 'add some users to the DB' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=$username --userid=$uid --bank=account1 --shares=1 &&
	flux account add-user --username=$username --userid=$uid --bank=account2 --shares=1 &&
	flux account add-user --username=user5011 --userid=5011 --bank=account1 --shares=1 &&
	flux account add-user --username=user5012 --userid=5012 --bank=account1 --shares=1
'

test_expect_success 'job-archive: set up config file' '
		cat >archive.toml <<EOF &&
[archive]
dbpath = "${ARCHIVEDB}"
period = "0.5s"
busytimeout = "0.1s"
EOF
	flux config reload
'

test_expect_success 'load job-archive module' '
	flux module load job-archive
'

test_expect_success 'submit a job that does not run' '
	job=$(flux submit --urgency=0 sleep 60) &&
	flux job wait-event -vt 10 $job priority &&
	flux cancel $job &&
	wait_db $job ${ARCHIVEDB}
'

test_expect_success 'run scripts to update job usage and fair-share' '
	flux account-fetch-job-records --copy ${ARCHIVEDB} -p ${DB_PATH} &&
	flux account -p ${DB_PATH} update-usage &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that usage does not get affected by canceled jobs' '
	flux account view-user --json $username > user.json &&
	test_debug "jq -S . <user.json" &&
	jq -e ".banks[0].job_usage == 0.0" <user.json
'

test_expect_success 'check that no jobs show up under user' '
	flux account -p ${DB_PATH} view-job-records --user $username > no_jobs.test &&
	test_cmp ${NO_JOBS} no_jobs.test
'

test_expect_success 'submit some jobs so they populate flux-core job-archive' '
	jobid1=$(flux submit -N 1 hostname) &&
	jobid2=$(flux submit -N 1 hostname) &&
	jobid3=$(flux submit -N 2 hostname) &&
	jobid4=$(flux submit -N 1 hostname) &&
	wait_db $jobid1 ${ARCHIVEDB} &&
	wait_db $jobid2 ${ARCHIVEDB} &&
	wait_db $jobid3 ${ARCHIVEDB} &&
	wait_db $jobid4 ${ARCHIVEDB}
'

test_expect_success 'call --copy argument to populate jobs table from job-archive DB' '
	flux account-fetch-job-records --copy ${ARCHIVEDB} -p ${DB_PATH} &&
	select_job_records ${DB_PATH} > records.out &&
	grep "hostname" records.out
'

test_expect_success 'submit some sleep 1 jobs under one user' '
	jobid1=$(flux submit -N 1 sleep 1) &&
	jobid2=$(flux submit -N 1 sleep 1) &&
	jobid3=$(flux submit -n 2 -N 2 sleep 1) &&
	wait_db $jobid1 ${ARCHIVEDB} &&
	wait_db $jobid2 ${ARCHIVEDB} &&
	wait_db $jobid3 ${ARCHIVEDB}
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'view job records for a user' '
	flux account -p ${DB_PATH} view-job-records --user $username
'

test_expect_success 'view job records for a user and direct it to a file' '
	flux account -p ${DB_PATH} --output-file $(pwd)/test.txt view-job-records --user $username
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account -p ${DB_PATH} update-usage &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > post_update1.test &&
	grep "account1" post_update1.test | grep "4" | grep "0.25"
'

test_expect_success 'submit some sleep 1 jobs under the secondary bank of the same user ' '
	jobid1=$(flux submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid2=$(flux submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid3=$(flux submit --setattr=system.bank=account2 -n 2 -N 2 sleep 1) &&
	wait_db $jobid1 ${ARCHIVEDB} &&
	wait_db $jobid2 ${ARCHIVEDB} &&
	wait_db $jobid3 ${ARCHIVEDB}
'

test_expect_success 'run custom job-list script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account -p ${DB_PATH} update-usage &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account -p ${DB_PATH} view-user $username --json > query1.json &&
	test_debug "jq -S . <query1.json" &&
	jq -e ".banks[1].job_usage >= 4" <query1.json
'

# if update-usage is called in the same half-life period when no jobs are found
# for a user, their job usage factor should be affected; this test is taken
# from the set of job-archive interface Python unit tests
test_expect_success 'call update-usage in the same half-life period where no jobs are run' '
	flux account -p ${DB_PATH} update-usage &&
	flux account-update-fshare -p ${DB_PATH} &&
	flux account -p ${DB_PATH} view-user $username --json > query2.json &&
	test_debug "jq -S . <query2.json" &&
	jq -e ".banks[1].job_usage >= 4" <query2.json
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'job-archive: unload module' '
	flux module unload job-archive
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
