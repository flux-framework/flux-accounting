#!/bin/bash

test_description='test validating job size compared to max resources limits'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association, configure its max resources limits' '
	flux account add-user \
		--username=user1 --userid=50001 --bank=A \
		--max-nodes=1 --max-cores=2
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job with a size greater than max_nodes limit' '
	test_must_fail flux python ${SUBMIT_AS} 50001 -N2 sleep 5 > max_nodes.out 2>&1 &&
	test_debug "cat max_nodes.out" &&
	grep \
		"job size (2 node(s), 2 core(s)) is greater than max resources limits
		 configured for association (1 node(s), 2 core(s))" max_nodes.out
'

test_expect_success 'submit a job with a size greater than max_cores limit' '
	test_must_fail flux python ${SUBMIT_AS} 50001 -n64 sleep 5 > max_cores.out 2>&1 &&
	test_debug "cat max_cores.out" &&
	grep \
		"job size (1 node(s), 64 core(s)) is greater than max resources limits
		 configured for association (1 node(s), 2 core(s))" max_cores.out
'

test_expect_success 'add a queue to the DB' '
	flux account add-queue bronze --max-nodes-per-assoc=1
'

test_expect_success 'edit association to belong to the queue' '
	flux account edit-user user1 --queues=bronze
'

test_expect_success 'configure flux with that queue' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'update plugin with new flux-accounting data' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job with a size greater than max_nodes_per_association limit on queue' '
	test_must_fail flux python ${SUBMIT_AS} 50001 \
		--queue=bronze -N2 sleep 5 > max_resources_queue.out 2>&1 &&
	test_debug "cat max_resources_queue.out" &&
	grep \
		"job size (2 node(s)) is greater than max resources limit configured
		 for queue (1 node(s))" max_resources_queue.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
