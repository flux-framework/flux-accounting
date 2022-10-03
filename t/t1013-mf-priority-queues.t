#!/bin/bash

test_description='Test multi-factor priority plugin queue support with a single user'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

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
	flux account -p ${DB_PATH} add-bank --parent-bank=root account1 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account2 1
'

test_expect_success 'add some queues to the DB' '
	flux account -p ${DB_PATH} add-queue standby --priority=0 &&
	flux account -p ${DB_PATH} add-queue expedite --priority=10000 &&
	flux account -p ${DB_PATH} add-queue bronze --priority=200 &&
	flux account -p ${DB_PATH} add-queue silver --priority=300 &&
	flux account -p ${DB_PATH} add-queue gold --priority=400
'

test_expect_success 'add a user to the DB' '
	flux account -p ${DB_PATH} add-user --username=user5011 \
		--userid=5011 --bank=account1 --queues="standby,bronze,silver,gold,expedite" &&
	flux account -p ${DB_PATH} add-user --username=user5011 \
		--userid=5011 --bank=account2 --queues="standby"
'

test_expect_success 'view user information' '
	flux account -p ${DB_PATH} view-user user5011
'

test_expect_success 'send the user and queue information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'users can run jobs without specifying a queue' '
	flux account -p ${DB_PATH} add-queue default --priority=1000 &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db &&
	jobid0=$(flux python ${SUBMIT_AS} 5011 -n1 hostname) &&
	flux job wait-event -f json $jobid0 priority | jq '.context.priority' > job0.test &&
	cat <<-EOF >job0.expected &&
	50000
	EOF
	test_cmp job0.expected job0.test &&
	flux job cancel $jobid0
'

# Include "foo" queue that accounting doesn't know about for test below
test_expect_success 'configure flux with those queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.standby]
	[queues.expedite]
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	[queues.foo]
	EOT
	flux config reload
'

test_expect_success 'submit a job using a queue the user does not belong to' '
	test_must_fail flux python ${SUBMIT_AS} 5011 --setattr=system.bank=account2 \
		--queue=expedite -n1 hostname > unavail_queue.out 2>&1 &&
	test_debug "unavail_queue.out" &&
	grep "Queue not valid for user: expedite" unavail_queue.out
'

test_expect_success 'submit a job using standby queue, which should not increase job priority' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 --job-name=standby \
		--setattr=system.bank=account1 --queue=standby -n1 hostname) &&
	flux job wait-event -f json $jobid1 priority | jq '.context.priority' > job1.test &&
	cat <<-EOF >job1.expected &&
	50000
	EOF
	test_cmp job1.expected job1.test
'

test_expect_success 'submit a job using expedite queue, which should increase priority' '
	jobid2=$(flux python ${SUBMIT_AS} 5011 --job-name=expedite \
		--setattr=system.bank=account1 --queue=expedite -n1 hostname) &&
	flux job wait-event -f json $jobid2 priority | jq '.context.priority' > job2.test &&
	cat <<-EOF >job2.expected &&
	100050000
	EOF
	test_cmp job2.expected job2.test
'

test_expect_success 'submit a job using the rest of the available queues' '
	jobid3=$(flux python ${SUBMIT_AS} 5011 --job-name=bronze --queue=bronze -n1 hostname) &&
	jobid4=$(flux python ${SUBMIT_AS} 5011 --job-name=silver --queue=silver -n1 hostname) &&
	jobid5=$(flux python ${SUBMIT_AS} 5011 --job-name=gold --queue=gold -n1 hostname)
'

test_expect_success 'check order of job queue' '
	flux jobs -A --suppress-header --format={name} > multi_queues.test &&
	cat <<-EOF >multi_queues.expected &&
	expedite
	gold
	silver
	bronze
	standby
	EOF
	test_cmp multi_queues.expected multi_queues.test
'

test_expect_success 'cancel existing jobs' '
	flux job cancel $jobid1 &&
	flux job cancel $jobid2 &&
	flux job cancel $jobid3 &&
	flux job cancel $jobid4 &&
	flux job cancel $jobid5
'

test_expect_success 'unload mf_priority.so' '
	flux jobtap remove mf_priority.so
'

test_expect_success 'submit a job to a nonexistent queue with no plugin information loaded' '
	jobid6=$(flux python ${SUBMIT_AS} 5011 --queue=foo -n1 hostname) &&
	test $(flux jobs -no {state} ${jobid6}) = PRIORITY
'

test_expect_success 'reload mf_priority.so and update it with the sample test data again' '
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	test $(flux jobs -no {state} ${jobid6}) = PRIORITY &&
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_done
