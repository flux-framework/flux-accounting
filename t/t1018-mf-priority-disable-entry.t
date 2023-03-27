#!/bin/bash

test_description='Test rejecting jobs from a user who has been disabled from the flux-accounting DB'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root account1 1 &&
	flux account add-bank --parent-bank=root account2 1
'

test_expect_success 'add a user with two different banks to the DB' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=$username --userid=$uid --bank=account1 --shares=1 &&
	flux account add-user --username=$username --userid=$uid --bank=account2 --shares=1
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job successfully under default bank' '
	jobid1=$(flux submit -n1 hostname) &&
	flux job wait-event -f json $jobid1 priority | jq '.context.priority' > job1.test &&
	cat <<-EOF >job1.expected &&
	50000
	EOF
	test_cmp job1.expected job1.test
'

test_expect_success 'submit a job successfully under second bank' '
	jobid2=$(flux submit --setattr=system.bank=account2 -n1 hostname) &&
	flux job wait-event -f json $jobid2 priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	50000
	EOF
	test_cmp job2.expected job2.test
'

test_expect_success 'disable second user/bank entry and update plugin' '
	flux account delete-user $username account2 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'try to submit job under second user/bank entry' '
	test_must_fail flux submit --setattr=system.bank=account2 -n1 hostname > deleted_entry1.out 2>&1 &&
	test_debug "cat deleted_entry1.out" &&
	grep "user/bank entry has been disabled from flux-accounting DB" deleted_entry1.out
'

test_expect_success 're-add second user/bank entry and update-plugin' '
	flux account add-user --username=$username --userid=$uid --bank=account2 --shares=1 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job successfully under second bank' '
	jobid3=$(flux submit --setattr=system.bank=account2 -n1 hostname) &&
	flux job wait-event -f json $jobid3 priority | jq '.context.priority' > job3.test &&
	cat <<-EOF >job3.expected &&
	50000
	EOF
	test_cmp job3.expected job3.test
'

test_expect_success 'disable first (and default) bank entry for user (will update the plugin with a new default bank)' '
	flux account delete-user $username account1 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'try to submit job under new default user/bank entry' '
	jobid4=$(flux submit -n1 hostname) &&
	flux job wait-event -f json $jobid4 priority | jq '.context.priority' > job4.test &&
	cat <<-EOF >job4.expected &&
	50000
	EOF
	test_cmp job4.expected job4.test
'

test_expect_success 'disabling a user while they have an active job should not kill the job' '
	jobid5=$(flux submit -n1 sleep 60) &&
	flux account delete-user $username account2 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db &&
	test $(flux jobs -no {state} ${jobid5}) = RUN &&
	flux job cancel $jobid5
'

test_expect_success 'trying to submit a job now should result in a job rejection' '
	test_must_fail flux submit --setattr=system.bank=account2 -n1 hostname > deleted_entry2.out 2>&1 &&
	test_debug "cat deleted_entry2.out" &&
	grep "user/bank entry has been disabled from flux-accounting DB" deleted_entry2.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
