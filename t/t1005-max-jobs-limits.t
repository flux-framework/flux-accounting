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
		"data" : [
			{"userid": 5011, "bank": "account3", "def_bank": "account3", "fairshare": 0.45321, "max_running_jobs": 2, "max_active_jobs": 4},
			{"userid": 5011, "bank": "account2", "def_bank": "account3", "fairshare": 0.11345, "max_running_jobs": 1, "max_active_jobs": 2}
		]
	}
	EOF
'

test_expect_success 'update plugin with sample test data' '
	flux python ${SEND_PAYLOAD} fake_user.json
'

test_expect_success 'submit max number of jobs' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 60)
'

test_expect_success 'submit job while already having max number of running jobs' '
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	test $(flux jobs -no {state} ${jobid3}) = DEPEND
'

test_expect_success 'a job transitioning to job.state.inactive should release a held job (if any)' '
	flux job cancel $jobid1 &&
	test $(flux jobs -no {state} ${jobid3}) = RUN &&
	flux job cancel $jobid2 &&
	flux job cancel $jobid3
'

test_expect_success 'submit max number of jobs with other bank' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60)
'

test_expect_success 'submit a job while already having max number of running jobs' '
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 sleep 60)
	test $(flux jobs -no {state} ${jobid2}) = DEPEND &&
	flux job cancel $jobid1 &&
	flux job cancel $jobid2
'

test_expect_success 'submit max number of jobs with a mix of default bank and explicity set bank' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account3 -n 1 sleep 60)
'

test_expect_success 'submit a job while already having max number of running jobs' '
	jobid3=$(flux python ${SUBMIT_AS} 5011 sleep 60) &&
	test $(flux jobs -no {state} ${jobid3}) = DEPEND &&
	flux job cancel $jobid3
'

test_expect_success 'increase the max jobs count of the user' '
	cat <<-EOF >new_max_running_jobs_limit.json
	{
		"data" : [
			{"userid": 5011, "bank": "account3", "def_bank": "account3", "fairshare": 0.45321, "max_running_jobs": 3, "max_active_jobs": 4}
		]
	}
	EOF
'

test_expect_success 'update plugin with same new sample test data' '
	flux python ${SEND_PAYLOAD} new_max_running_jobs_limit.json
'

test_expect_success 'make sure jobs are still running' '
	test $(flux jobs -no {state} ${jobid1}) = RUN &&
	test $(flux jobs -no {state} ${jobid2}) = RUN
'

test_expect_success 'cancel all remaining jobs' '
	flux job cancel ${jobid1} &&
	flux job cancel ${jobid2}
'

test_done
