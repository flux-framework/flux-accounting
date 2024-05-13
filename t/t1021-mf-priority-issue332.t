#!/bin/bash

test_description='Test submitting jobs to queues after queue access is changed'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/plugin_state

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'
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
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze --priority=200 &&
	flux account add-queue silver --priority=300 &&
	flux account add-queue gold   --priority=400
'

test_expect_success 'configure flux with those queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload &&
	flux queue stop --all
'

test_expect_success 'add a user to the DB' '
	flux account add-user --username=user1001 --userid=1001 --bank=A --queues="bronze,silver,gold" &&
	flux account view-user user1001
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job while specifying a queue' '
	flux python ${SUBMIT_AS} 1001 -n1 --queue=bronze hostname
'

test_expect_success 'edit a user to no longer have access to any of the added queues' '
	flux account edit-user user1001 --bank=A --queues=
'

test_expect_success 're-send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submitting a job while specifying a queue they no longer have access to should be rejected' '
	test_must_fail flux python ${SUBMIT_AS} 1001 -n1 --queue=bronze hostname > no_queue_access.out 2>&1 &&
	grep "Queue not valid for user: bronze" no_queue_access.out
'

test_expect_success 're-add the available queues to the user' '
	flux account edit-user user1001 --bank=A --queues="bronze,silver,gold"
'

test_expect_success 're-send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submit a job while specifying a queue' '
	flux python ${SUBMIT_AS} 1001 -n1 --queue=bronze hostname
'

test_expect_success 'delete the queues from the flux-accounting database and from the user' '
	flux account delete-queue bronze &&
	flux account delete-queue silver &&
	flux account delete-queue gold &&
	flux account edit-user user1001 --bank=A --queues=
'

test_expect_success 're-send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submitting a job should now skip the check for queue validation' '
	flux python ${SUBMIT_AS} 1001 -n1 --queue=bronze hostname
'

test_expect_success 're-add those queues to the DB' '
	flux account add-queue bronze --priority=200 &&
	flux account add-queue silver --priority=300 &&
	flux account add-queue gold   --priority=400
'

test_expect_success 're-send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'submitting a job specifying a queue should now trigger queue validation' '
	test_must_fail flux python ${SUBMIT_AS} 1001 -n1 --queue=bronze hostname > no_queue_access2.out 2>&1 &&
	grep "Queue not valid for user: bronze" no_queue_access2.out
'

test_expect_success 'submitting a job to a nonexistent queue should be rejected' '
	test_must_fail flux python ${SUBMIT_AS} 1001 -n1 --queue=foo hostname > no_such_queue.out 2>&1 &&
	grep "flux-job: Invalid queue '\''foo'\'' specified" no_such_queue.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
