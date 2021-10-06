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

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create fake_user.json' '
	cat <<-EOF >fake_user.json
	{
		"users" : [
			{"userid": "5011", "bank": "account3", "default_bank": "account3", "fairshare": "0.45321", "max_jobs": "3"},
			{"userid": "5011", "bank": "account2", "default_bank": "account3", "fairshare": "0.11345", "max_jobs": "2"}
		]
	}
	EOF
'

test_expect_success 'update plugin with sample test data' '
	flux python ${SEND_PAYLOAD} fake_user.json
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'submit max number of jobs' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success 'submit a job while already having max number of active jobs' '
	test_must_fail flux python ${SUBMIT_AS} 5011 sleep 60 > max_jobs.out 2>&1 &&
	test_debug "cat max_jobs.out" &&
	grep "user has max number of jobs submitted" max_jobs.out &&
	flux job cancel $jobid1 &&
	flux job cancel $jobid2 &&
	flux job cancel $jobid3
'

test_expect_success 'submit max number of jobs with other bank' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60)
'

test_expect_success 'submit a job while already having max number of active jobs' '
	test_must_fail flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60 > max_jobs.out 2>&1 &&
	test_debug "cat max_jobs.out" &&
	grep "user has max number of jobs submitted" max_jobs.out &&
	flux job cancel $jobid1 &&
	flux job cancel $jobid2
'

test_expect_success 'submit max number of jobs with a mix of default bank and explicity set bank' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account3 sleep 60) &&
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success 'submit a job while already having max number of active jobs' '
	test_must_fail flux python ${SUBMIT_AS} 5011 sleep 60 > max_jobs.out 2>&1 &&
	test_debug "cat max_jobs.out" &&
	grep "user has max number of jobs submitted" max_jobs.out
'

test_expect_success 'increase the max jobs count of the user' '
	cat <<-EOF >new_max_jobs_limit.json
	{
		"users" : [
			{"userid": "5011", "bank": "account3", "default_bank": "account3", "fairshare": "0.45321", "max_jobs": "4"}
		]
	}
	EOF
'

test_expect_success 'update plugin with same sample test data; this should not reset current jobs count' '
	flux python ${SEND_PAYLOAD} new_max_jobs_limit.json
'

test_expect_success 'submit a job successfully under the new max jobs limit' '
	jobid4=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	test_must_fail flux python ${SUBMIT_AS} 5011 sleep 60 > max_jobs.out 2>&1 &&
	test_debug "cat max_jobs.out" &&
	grep "user has max number of jobs submitted" max_jobs.out &&
	flux job cancel $jobid1 &&
	flux job cancel $jobid2 &&
	flux job cancel $jobid3 &&
	flux job cancel $jobid4
'

test_done
