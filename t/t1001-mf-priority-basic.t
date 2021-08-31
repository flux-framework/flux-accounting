#!/bin/bash

test_description='Test multi-factor priority plugin with a single user'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so

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

test_expect_success 'try to submit a job when user does not exist in DB' '
	test_must_fail flux mini submit -n1 hostname > failure.out 2>&1 &&
	test_debug "cat failure.out" &&
	grep "user not found in flux-accounting DB" failure.out
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

	username = getpass.getuser()
	userid = pwd.getpwnam(username).pw_uid
	# create a JSON payload
	data = {"userid": str(userid), "bank": "account3", "default_bank": "account3", "fairshare": "0.45321", "max_jobs": "10"}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", data).get()
	data = {"userid": str(userid), "bank": "account2", "default_bank": "account3", "fairshare": "0.11345", "max_jobs": "10"}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", data).get()
	EOF
'

test_expect_success 'update plugin with sample test data' '
	flux python fake_payload.py
'

test_expect_success 'submit a job with default urgency' '
	jobid=$(flux mini submit --setattr=system.bank=account3 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job1.test &&
	cat <<-EOF >job1.expected &&
	45321
	EOF
	test_cmp job1.expected job1.test
'

test_expect_success 'submit a job with custom urgency' '
	jobid=$(flux mini submit --setattr=system.bank=account3 --urgency=15 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	45320
	EOF
	test_cmp job2.expected job2.test
'

test_expect_success 'submit a job with urgency of 0' '
	jobid=$(flux mini submit --setattr=system.bank=account3 --urgency=0 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job3.test &&
	cat <<-EOF >job3.expected &&
	0
	EOF
	test_cmp job3.expected job3.test &&
	flux job cancel $jobid
'

test_expect_success 'submit a job with urgency of 31' '
	jobid=$(flux mini submit --setattr=system.bank=account3 --urgency=31 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job4.test &&
	cat <<-EOF >job4.expected &&
	4294967295
	EOF
	test_cmp job4.expected job4.test
'

test_expect_success 'submit a job with other bank' '
	jobid=$(flux mini submit --setattr=system.bank=account2 -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job5.test &&
	cat <<-EOF >job5.expected &&
	11345
	EOF
	test_cmp job5.expected job5.test
'

test_expect_success 'submit a job using default bank' '
	jobid=$(flux mini submit -n1 hostname) &&
	flux job wait-event -f json $jobid priority | jq '.context.priority' > job6.test &&
	cat <<-EOF >job6.expected &&
	45321
	EOF
	test_cmp job6.expected job6.test
'

test_expect_success 'submit a job using a bank the user does not belong to' '
	test_must_fail flux mini submit --setattr=system.bank=account1 -n1 hostname > bad_bank.out 2>&1 &&
	test_debug "cat bad_bank.out" &&
	grep "user does not belong to specified bank" bad_bank.out
'

test_expect_success 'reject job when invalid bank format is passed in' '
	test_must_fail flux mini submit --setattr=system.bank=1 -n1 hostname > invalid_fmt.out 2>&1 &&
	test_debug "cat invalid_fmt.out" &&
	grep "unable to unpack bank arg" invalid_fmt.out
'

test_expect_success 'create a fake payload with an empty fairshare key-value pair' '
	cat <<-EOF >empty_fairshare.py
	import flux
	import pwd
	import getpass

	username = getpass.getuser()
	userid = pwd.getpwnam(username).pw_uid
	# create a JSON payload
	data = {"userid": str(userid), "bank": "account4", "default_bank": "account3", "fairshare": "", "max_jobs": "10"}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", data).get()
	EOF
'

test_expect_success 'update plugin with sample test data' '
	flux python empty_fairshare.py
'

test_expect_success 'submit a job with new bank and 0 fairshare should result in a job rejection' '
	test_must_fail flux mini submit --setattr=system.bank=account4 hostname > zero_fairshare.out 2>&1 &&
	test_debug "zero_fairshare.out" &&
	grep "user fairshare value is 0" zero_fairshare.out
'

test_done
