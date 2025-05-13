#!/bin/bash

test_description='Test cancelling active jobs with a late user/bank info load'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit a number of jobs with no user/bank info loaded to plugin' '
	jobid1=$(flux submit --wait-event=depend hostname) &&
	jobid2=$(flux submit --wait-event=depend hostname) &&
	jobid3=$(flux submit --wait-event=depend hostname)
'

test_expect_success 'make sure jobs get held in state PRIORITY' '
	flux job wait-event -vt 60 ${jobid1} depend &&
	flux job wait-event -vt 60 ${jobid2} depend &&
	flux job wait-event -vt 60 ${jobid3} depend
'

test_expect_success 'cancel held jobs' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3}
'

test_expect_success 'submit job #1 with no user/bank info loaded to plugin' '
	jobid1=$(flux submit --wait-event=depend hostname)
'

test_expect_success 'check that job #1 is in state PRIORITY' '
	flux job wait-event -vt 60 ${jobid1} depend
'

test_expect_success 'send the user/bank information to the plugin without reprioritizing all active jobs' '
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
				"max_running_jobs": 10,
				"max_active_jobs": 12,
				"max_nodes": 2147483647,
				"max_cores": 2147483647,
				"queues": "standby,special",
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
	EOF
	flux python fake_payload.py
'

test_expect_success 'submit job #2 which should run before job #1' '
	jobid2=$(flux submit hostname) &&
	flux job wait-event -t 15 ${jobid2} clean
'

test_expect_success 'cancel job #1' '
	flux cancel ${jobid1}
'

test_done
