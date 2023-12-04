#!/bin/bash

test_description='Test multi-factor priority plugin with a single user'

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

test_expect_success 'send an empty payload to make sure unpack fails' '
	cat <<-EOF >bad_payload.py &&
	import flux

	#create a JSON payload
	flux.Flux().rpc("job-manager.mf_priority.rec_update", {}).get()
	EOF
	test_must_fail flux python bad_payload.py &&
	flux dmesg | grep "failed to unpack custom_priority.trigger msg: Protocol error"
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
				"max_running_jobs": 10,
				"max_active_jobs": 12,
				"queues": "standby,special"
			},
			{
				"userid": userid,
				"bank": "account2",
				"def_bank": "account3",
				"fairshare": 0.11345,
				"max_running_jobs": 10,
				"max_active_jobs": 12,
				"queues": "standby"
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
'

test_expect_success 'update plugin with sample test data' '
	flux python fake_payload.py
'

test_expect_success 'submit a job with default urgency' '
	jobid=$(flux submit --setattr=system.bank=account3 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job1.test &&
	cat <<-EOF >job1.expected &&
	45321
	EOF
	test_cmp job1.expected job1.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job with custom urgency' '
	jobid=$(flux submit --setattr=system.bank=account3 --urgency=15 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	45320
	EOF
	test_cmp job2.expected job2.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job with urgency of 0' '
	jobid=$(flux submit --setattr=system.bank=account3 --urgency=0 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job3.test &&
	cat <<-EOF >job3.expected &&
	0
	EOF
	test_cmp job3.expected job3.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job with urgency of 31' '
	jobid=$(flux submit --setattr=system.bank=account3 --urgency=31 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job4.test &&
	cat <<-EOF >job4.expected &&
	4294967295
	EOF
	test_cmp job4.expected job4.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job with other bank' '
	jobid=$(flux submit --setattr=system.bank=account2 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job5.test &&
	cat <<-EOF >job5.expected &&
	11345
	EOF
	test_cmp job5.expected job5.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job using default bank' '
	jobid=$(flux submit -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job6.test &&
	cat <<-EOF >job6.expected &&
	45321
	EOF
	test_cmp job6.expected job6.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job using a bank the user does not belong to' '
	test_must_fail flux submit --setattr=system.bank=account1 -n1 hostname > bad_bank.out 2>&1 &&
	test_debug "cat bad_bank.out" &&
	grep "cannot find user/bank or user/default bank entry for:" bad_bank.out
'

test_expect_success 'reject job when invalid bank format is passed in' '
	test_must_fail flux submit --setattr=system.bank=1 -n1 hostname > invalid_fmt.out 2>&1 &&
	test_debug "cat invalid_fmt.out" &&
	grep "unable to unpack bank arg" invalid_fmt.out
'

test_expect_success 'pass special key to user/bank struct to nullify information' '
	cat <<-EOF >null_struct.json
	{
		"data" : [
			{
				"userid": 5011,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": -1,
				"max_active_jobs": 12,
				"queues": "standby,special"
			}
		]
	}
	EOF
	flux python ${SEND_PAYLOAD} null_struct.json
'

test_expect_success 'submit job with NULL user/bank information' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 sleep 10)
'

test_expect_success 'ensure exception was raised in job.state.depend and job is canceled' '
	flux job wait-event -v ${jobid1} exception > exception.test &&
	grep "job.state.depend: bank info is missing" exception.test
'

test_expect_success 'resend user/bank information with valid data and successfully submit a job' '
	cat <<-EOF >valid_info.json
	{
		"data" : [
			{
				"userid": 5011,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 2,
				"max_active_jobs": 4,
				"queues": "standby,special"
			}
		]
	}
	EOF
	flux python ${SEND_PAYLOAD} valid_info.json &&
	jobid2=$(flux python ${SUBMIT_AS} 5011 sleep 10)
	flux job wait-event -f json $jobid2 priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	45321
	EOF
	test_cmp job2.expected job2.test &&
	flux job cancel $jobid2
'

test_done
