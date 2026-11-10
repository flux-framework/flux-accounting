#!/bin/bash

test_description='Test cancelling active jobs with a late user/bank info load'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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
				"def_project": "*",
				"max_sched_jobs": 2147483647
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(bulk_update_data)).get()
	bulk_queue_data = {
		"data" : [
			{
				"queue": "default",
				"priority": 0,
				"max_running_jobs": 2147483647,
				"max_sched_jobs": 2147483647,
				"max_sched_nodes_per_assoc": 2147483647,
				"max_sched_cores_per_assoc": 2147483647
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
	flux cancel ${jobid1} &&
	flux job wait-event -t 15 ${jobid1} clean
'

# Unlike replayed jobs, live submissions already have a Job aux item and an
# active-job charge on DNE. This set of tests makes sure that the transfer
# of the job just moves the charges instead of duplicating them
test_expect_success 'reload without accounting data and hold the unnamed queue' '
	flux jobtap load -r mf_priority.so ${MULTI_FACTOR_PRIORITY} &&
	flux python <<-EOF
	import flux
	flux.Flux().rpc("job-manager.mf_priority.rec_q_update", {
	    "data": [{
	        "queue": "",
	        "priority": 0,
	        "max_running_jobs": 0,
	        "max_sched_jobs": 2147483647,
	        "max_sched_nodes_per_assoc": 2147483647,
	        "max_sched_cores_per_assoc": 2147483647,
	    }],
	}).get()
	EOF
'

test_expect_success 'live jobs share the provisional active-job count' '
	live1=$(flux submit sleep inf) &&
	live2=$(flux submit sleep inf) &&
	for id in ${live1} ${live2}; do
		flux job wait-event -t 15 \
			--match-context=description=max-run-jobs-queue \
			${id} dependency-add || return 1
	done &&
	flux jobtap query mf_priority.so >provisional.json &&
	jq -e ".mf_priority_map[].banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 2 and (.held_jobs | length) == 2" provisional.json
'

test_expect_success 'late data releases live jobs and transfers their charges' '
	flux python fake_payload.py &&
	flux python <<-EOF
	import flux
	h = flux.Flux()
	# lift the hold on the queue explicitly
	h.rpc("job-manager.mf_priority.rec_q_update", {
	    "data": [{
	        "queue": "",
	        "priority": 0,
	        "max_running_jobs": 2147483647,
	        "max_sched_jobs": 2147483647,
	        "max_sched_nodes_per_assoc": 2147483647,
	        "max_sched_cores_per_assoc": 2147483647,
	    }],
	}).get()
	h.rpc("job-manager.mf_priority.reprioritize").get()
	EOF
'

test_expect_success 'both live jobs leave DEPEND with no charge left on DNE' '
	flux job wait-event -t 15 ${live1} priority &&
	flux job wait-event -t 15 ${live2} priority &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[].banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0 and (.held_jobs | length) == 0" query.json &&
	jq -e ".mf_priority_map[].banks[] |
		select(.bank_name == \"account3\") | .cur_active_jobs == 2" query.json
'

test_expect_success 'cancelling resolved live jobs balances active counts' '
	flux cancel ${live1} ${live2} &&
	flux job wait-event -t 15 ${live1} clean &&
	flux job wait-event -t 15 ${live2} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e "all(.mf_priority_map[].banks[];
		.cur_active_jobs == 0 and (.held_jobs | length) == 0)" query.json
'

test_done
