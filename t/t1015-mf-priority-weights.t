#!/bin/bash

test_description='Test configuring plugin weights and their effects on priority calculation'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

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

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account1 1
'

test_expect_success 'add a default queue to the DB' '
	flux account -p ${DB_PATH} add-queue default --priority=100
'

test_expect_success 'add a user to the DB' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account -p ${DB_PATH} add-user --username=$username --userid=$uid --bank=account1 --shares=1
'

test_expect_success 'view queue information' '
	flux account -p ${DB_PATH} view-plugin-factor fairshare > fshare_weight.test &&
	grep "fairshare          100000" fshare_weight.test &&
	flux account -p ${DB_PATH} view-plugin-factor queue > queue_weight.test &&
	grep "queue              10000" queue_weight.test
'

test_expect_success 'send the user, queue, and plugin factor weight information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job using default fshare and queue factor weights' '
	jobid1=$(flux mini submit -n1 hostname) &&
	flux job wait-event -f json $jobid1 priority | jq '.context.priority' > job1.test &&
	cat <<-EOF >job1.expected &&
	1050000
	EOF
	test_cmp job1.expected job1.test
'

test_expect_success 'edit plugin factor weights to give fairshare all the weight' '
	flux account -p ${DB_PATH} edit-plugin-factor fairshare --weight=1000 &&
	flux account -p ${DB_PATH} edit-plugin-factor queue --weight=0 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job using the new fshare and queue factor weights' '
	jobid2=$(flux mini submit -n1 hostname) &&
	flux job wait-event -f json $jobid2 priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	500
	EOF
	test_cmp job2.expected job2.test
'

test_expect_success 'edit plugin factor weights to give queue all the weight' '
	flux account -p ${DB_PATH} edit-plugin-factor fairshare --weight=0 &&
	flux account -p ${DB_PATH} edit-plugin-factor queue --weight=1000 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job using the new fshare and queue factor weights' '
	jobid3=$(flux mini submit -n1 hostname) &&
	flux job wait-event -f json $jobid3 priority | jq '.context.priority' > job3.test &&
	cat <<-EOF >job3.expected &&
	100000
	EOF
	test_cmp job3.expected job3.test
'

test_done
