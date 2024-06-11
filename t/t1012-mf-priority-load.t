#!/bin/bash

test_description='Test multi-factor priority plugin and loading user information late'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py

mkdir -p config
export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'disable age factor in multi-factor priority plugin' '
	cat >config/test.toml <<-EOT &&
	[accounting.factor-weights]
	age = 0
	EOT
	flux config reload
'

test_expect_success 'create fake_payload.py' '
	cat <<-EOF >fake_payload.py
	import flux
	import pwd
	import getpass
	import json

	username = getpass.getuser()
	userid = pwd.getpwnam(username).pw_uid
	# create an array of JSON payloads
	bulk_update_data = {
		"data" : [
			{
				"userid": userid,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 1,
				"max_active_jobs": 3,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*"
			},
			{
				"userid": userid,
				"bank": "account2",
				"def_bank": "account3",
				"fairshare": 0.11345,
				"max_running_jobs": 1,
				"max_active_jobs": 3,
				"queues": "",
				"active": 1,
				"projects": "*",
				"def_project": "*"
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(bulk_update_data)).get()
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
	flux.Flux().rpc("job-manager.mf_priority.reprioritize")
	EOF
'

test_expect_success 'submitting a job specifying an incorrect bank with no user data results in a job exception' '
	jobid0=$(flux submit --setattr=system.bank=account4 -n1 sleep 60) &&
	flux python fake_payload.py &&
	flux job wait-event -v ${jobid0} exception > exception.test &&
	grep "cannot find user/bank or user/default bank entry for uid:" exception.test
'

test_expect_success 'unload and reload mf_priority.so' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit sleep 60 jobs with no data update' '
	jobid1=$(flux submit -n1 sleep 60)
'

test_expect_success 'check that submitted job is in state PRIORITY' '
	flux job wait-event -vt 60 ${jobid1} depend
'

test_expect_success 'update plugin with sample test data again' '
	flux python fake_payload.py
'

test_expect_success 'check that previously held job transitions to RUN' '
	flux job wait-event -vt 60 ${jobid1} alloc
'

test_expect_success 'submit 2 more sleep jobs' '
	jobid2=$(flux submit -n1 sleep 60) &&
	jobid3=$(flux submit -n1 sleep 60)
'

test_expect_success 'check flux jobs - should have 1 running job, 2 pending jobs' '
	flux job wait-event -vt 60 ${jobid1} alloc &&
	flux job wait-event -vt 60 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobid2} dependency-add &&
	flux job wait-event -vt 60 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobid3} dependency-add
'

test_expect_success 'cancel running jobs one at a time and check that each pending job transitions to RUN' '
	flux cancel ${jobid1} &&
	flux job wait-event -vt 60 ${jobid2} alloc &&
	flux cancel ${jobid2} &&
	flux job wait-event -vt 60 ${jobid3} alloc &&
	flux cancel ${jobid3}
'

test_expect_success 'unload mf_priority.so' '
	flux jobtap remove mf_priority.so
'

test_expect_success 'submit a job with no plugin loaded' '
	jobid4=$(flux submit -n 1 sleep 60) &&
	flux job wait-event -vt 60 ${jobid4} depend
'

test_expect_success 'reload mf_priority.so with a job still in job.state.priority' '
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	flux job wait-event -vt 60 ${jobid4} depend
'

test_expect_success 'update plugin with sample test data again' '
	flux python fake_payload.py
'

test_expect_success 'check that originally pending job transitions to RUN' '
	flux job wait-event -vt 60 ${jobid4} alloc &&
	flux cancel ${jobid4}
'

test_done
