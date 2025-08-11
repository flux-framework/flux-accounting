#!/bin/bash

test_description='test fetching jobs and updating the fair share values for a group of users'

. $(dirname $0)/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"
NO_JOBS=${SHARNESS_TEST_SRCDIR}/expected/job_usage/no_jobs.expected

export FLUX_CONF_DIR=$(pwd)
test_under_flux 4 job

flux setattr log-stderr-level 1

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

test_expect_success 'submit a job that does not run' '
	job=$(flux submit --urgency=0 sleep 60) &&
	flux job wait-event -vt 10 ${job} priority &&
	flux cancel ${job}
'

test_expect_success 'run scripts to update job usage and fair-share' '
	flux account-fetch-job-records -p ${DB_PATH} &&
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that usage does not get affected by canceled jobs' '
	flux account view-user $username > user.json &&
	test_debug "jq -S . <user.json" &&
	jq -e ".[0].job_usage == 0.0" <user.json
'

test_expect_success 'check that no jobs show up under user' '
	flux account -p ${DB_PATH} view-job-records --user $username > no_jobs.test &&
	cat <<-EOF >no_jobs.expected &&
	jobid           | username | userid   | t_submit        | t_run           | t_inactive      | nnodes   | project  | bank
	EOF
	grep -f no_jobs.expected no_jobs.test
'

test_expect_success 'submit some jobs and wait for them to finish running' '
	jobid1=$(flux submit -N 1 hostname) &&
	jobid2=$(flux submit -N 1 hostname) &&
	jobid3=$(flux submit -N 2 hostname) &&
	jobid4=$(flux submit -N 1 hostname) &&
	flux job wait-event -vt 3 ${jobid1} clean &&
	flux job wait-event -vt 3 ${jobid2} clean &&
	flux job wait-event -vt 3 ${jobid3} clean &&
	flux job wait-event -vt 3 ${jobid4} clean
'

test_expect_success 'run fetch-job-records; ensure jobs show up in jobs table' '
	flux account-fetch-job-records -p ${DB_PATH} &&
	select_job_records ${DB_PATH} > records.out &&
	grep "hostname" records.out
'

test_expect_success 'submit some sleep 1 jobs under one user' '
	jobid1=$(flux submit -N 1 sleep 1) &&
	jobid2=$(flux submit -N 1 sleep 1) &&
	jobid3=$(flux submit -n 2 -N 2 sleep 1) &&
	flux job wait-event -vt 3 ${jobid1} clean &&
	flux job wait-event -vt 3 ${jobid2} clean &&
	flux job wait-event -vt 3 ${jobid3} clean
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account view-bank account1 -t > post_update1.test &&
	grep "account1" post_update1.test | grep "4" | grep "0.25"
'

test_expect_success 'submit some sleep 1 jobs under the secondary bank of the same user ' '
	jobid1=$(flux submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid2=$(flux submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid3=$(flux submit --setattr=system.bank=account2 -n 2 -N 2 sleep 1) &&
	flux job wait-event -vt 3 ${jobid1} clean &&
	flux job wait-event -vt 3 ${jobid2} clean &&
	flux job wait-event -vt 3 ${jobid3} clean
'

test_expect_success 'run custom job-list script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account -p ${DB_PATH} view-user $username > query1.json &&
	test_debug "jq -S . <query1.json" &&
	jq -e ".[1].job_usage >= 4" <query1.json
'

# if update-usage is called in the same half-life period when no jobs are found
# for a user, their job usage factor should not be affected; this test is taken
# from the set of job-archive interface Python unit tests
test_expect_success 'call update-usage in the same half-life period where no jobs are run' '
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH} &&
	flux account -p ${DB_PATH} view-user $username > query2.json &&
	test_debug "jq -S . <query2.json" &&
	jq -e ".[1].job_usage >= 4" <query2.json
'

test_expect_success 'call view-job-records with custom format string' '
	flux account view-job-records -o "{userid:<8} || {t_inactive:<12.3f}"
'

test_expect_success 'call view-job-records -o with an invalid field' '
	test_must_fail flux account view-job-records -o "{foo}" > invalid_field.out 2>&1 &&
	grep "Unknown format field: foo" invalid_field.out
'

# ensure that job usage factors are displayed with -j/--job-usage;
# make sure that both rows have job usage values of at least 4 in the
# most recent job usage factor column
test_expect_success 'call view-user -J/--job-usage' '
	flux account view-user -J ${username} > job_usage_breakdown.json &&
	test_debug "jq -S . <job_usage_breakdown.json" &&
	jq -e ".[0].usage_factor_period_0 >= 4" job_usage_breakdown.json &&
	jq -e ".[1].usage_factor_period_0 >= 4" job_usage_breakdown.json
'

test_expect_success 'pass both -J and --fields; ensure ValueError is raised' '
	test_must_fail flux account view-user --fields=username -J ${username} > bad_args.error 2>&1 &&
	grep "argument \-J/\-\-job-usage: not allowed with argument \-\-fields" bad_args.error
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
