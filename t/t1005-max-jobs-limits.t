#!/bin/bash

test_description='Test per-user max jobs limits'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

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

test_expect_success 'create fake_user.json' '
	cat <<-EOF >fake_user.json
	{
		"data" : [
			{
				"userid": 5011,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 2,
				"max_active_jobs": 4,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			},
			{
				"userid": 5011,
				"bank": "account2",
				"def_bank": "account3",
				"fairshare": 0.11345,
				"max_running_jobs": 1,
				"max_active_jobs": 2,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			}
		]
	}
	EOF
'

test_expect_success 'update plugin with sample test data' '
	flux python ${SEND_PAYLOAD} fake_user.json
'

test_expect_success 'add a default queue and send it to the plugin' '
	cat <<-EOF >fake_payload.py
	import flux
	import json

	bulk_queue_data = {
		"data" : [
			{
				"queue": "default",
				"priority": 0,
				"min_nodes_per_job": 0,
				"max_nodes_per_job": 5,
				"max_time_per_job": 64000
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_q_update", json.dumps(bulk_queue_data)).get()
	EOF
	flux python fake_payload.py
'

# The following set of tests will check that the priority plugin enforces
# accounting limits defined per-association in the flux-accounting database,
# specifically an association's max running jobs and max active jobs limit.
# When the association hits their max running jobs limit, subsequently
# submitted jobs will be held by having an accounting-specific dependency added
# to it. Once they hit their max active jobs limit, subsequently submitted jobs
# will be rejected with an accounting-specific rejection message.
test_expect_success 'submit max number of jobs' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success 'a submitted job while at max-running-jobs limit will have a dependency added to it' '
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	flux job wait-event -vt 60 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobid3} dependency-add
'

test_expect_success 'a job transitioning to job.state.inactive should release a held job (if any)' '
	flux cancel ${jobid1} &&
	flux job wait-event -vt 60 ${jobid3} alloc &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3}
'

test_expect_success 'submit max number of jobs with other bank' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60)
'

test_expect_success 'a submitted job while at max-running-jobs limit will have a dependency added to it' '
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60) &&
	flux job wait-event -vt 60 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobid2} dependency-add &&
	flux cancel ${jobid1} &&
	flux cancel ${jobid2}
'

test_expect_success 'submit max number of jobs to the same bank (explicitly and by default)' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account3 -n 1 sleep 60)
'

test_expect_success 'a submitted job while at max-running-jobs limit will have a dependency added to it' '
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	flux job wait-event -vt 60 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobid3} dependency-add &&
	flux cancel ${jobid3}
'

test_expect_success 'increase the max jobs count of the user' '
	cat <<-EOF >new_max_running_jobs_limit.json
	{
		"data" : [
			{
				"userid": 5011,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 3,
				"max_active_jobs": 4,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			}
		]
	}
	EOF
'

test_expect_success 'update plugin with same new sample test data' '
	flux python ${SEND_PAYLOAD} new_max_running_jobs_limit.json
'

test_expect_success 'make sure jobs are still running' '
	flux job wait-event -vt 10 ${jobid1} alloc &&
	flux job wait-event -vt 10 ${jobid2} alloc
'

test_expect_success 'cancel all remaining jobs' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid2}
'

test_expect_success 'submit max number of jobs' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid4=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success '5th submitted job should be rejected because user has reached max_active_jobs limit' '
	test_must_fail flux python ${SUBMIT_AS} 5011 sleep 60 > max_active_jobs.out 2>&1 &&
	test_debug "cat max_active_jobs.out" &&
	grep "user has max active jobs" max_active_jobs.out &&
	flux cancel ${jobid1} &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3} &&
	flux cancel ${jobid4}
'

test_expect_success 'update max_active_jobs limit' '
	cat <<-EOF >new_max_active_jobs_limit.json
	{
		"data" : [
			{
				"userid": 5011,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 3,
				"max_active_jobs": 5,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			}
		]
	}
	EOF
'

test_expect_success 'update plugin with same new sample test data' '
	flux python ${SEND_PAYLOAD} new_max_active_jobs_limit.json
'

test_expect_success 'submit max number of jobs' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid4=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid5=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success '6th submitted job should be rejected because user has reached new max_active_jobs limit' '
	test_must_fail flux python ${SUBMIT_AS} 5011 sleep 60 > max_active_jobs.out 2>&1 &&
	test_debug "cat max_active_jobs.out" &&
	grep "user has max active jobs" max_active_jobs.out
'

test_expect_success 'cancel one of the active jobs' '
	flux cancel ${jobid5}
'

test_expect_success 'newly submitted job should now be accepted since user is under their max_active_jobs limit' '
	jobid7=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	flux job wait-event -f json ${jobid7} priority | jq '.context.priority' > job7.test &&
	cat <<-EOF >job7.expected &&
	45321
	EOF
	test_cmp job7.expected job7.test
'

test_expect_success 'cancel all remaining active jobs' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3} &&
	flux cancel ${jobid4} &&
	flux cancel ${jobid7}
'

test_expect_success 'create another user with the same limits in multiple banks' '
	cat <<-EOF >fake_user2.json
	{
		"data" : [
			{
				"userid": 5012,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 1,
				"max_active_jobs": 2,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			},
			{
				"userid": 5012,
				"bank": "account2",
				"def_bank": "account3",
				"fairshare": 0.11345,
				"max_running_jobs": 1,
				"max_active_jobs": 2,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_nodes": 2147483647,
				"max_cores": 2147483647
			}
		]
	}
	EOF
'

test_expect_success 'update plugin with new user data' '
	flux python ${SEND_PAYLOAD} fake_user2.json
'

test_expect_success 'submit max number of jobs under both banks' '
	jobid1=$(flux python ${SUBMIT_AS} 5012 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5012 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 5012 --setattr=system.bank=account2 sleep 60) &&
	jobid4=$(flux python ${SUBMIT_AS} 5012 --setattr=system.bank=account2 sleep 60)
'

test_expect_success 'submitting a 3rd job under either bank should result in a job rejection' '
	test_must_fail flux python ${SUBMIT_AS} 5012 sleep 60 > max_active_jobs.out 2>&1 &&
	test_debug "cat max_active_jobs.out" &&
	grep "user has max active jobs" max_active_jobs.out &&
	test_must_fail flux python ${SUBMIT_AS} 5012 --setattr=system.bank=account2 sleep 60 > max_active_jobs2.out 2>&1 &&
	test_debug "cat max_active_jobs2.out" &&
	grep "user has max active jobs" max_active_jobs2.out
'

test_expect_success 'cancel all remaining jobs' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3} &&
	flux cancel ${jobid4}
'

test_done
