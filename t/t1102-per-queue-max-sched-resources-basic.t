#!/bin/bash

test_description='test managing the per-queue total max-nodes/cores property'

. `dirname $0`/sharness.sh

mkdir -p config

DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'view-queue: default max_nodes/cores values show up' '
	flux account add-queue q1 &&
	flux account view-queue q1 > view_queue1.out &&
	grep "\"max_nodes\": \"unlimited\"" view_queue1.out &&
	grep "\"max_cores\": \"unlimited\"" view_queue1.out
'

test_expect_success 'view-queue: configured max_nodes/cores values show up' '
	flux account add-queue q2 \
		--max-nodes=8765 \
		--max-cores=4321 &&
	flux account view-queue q2 > view_queue2.out &&
	grep "\"max_nodes\": 8765" view_queue2.out &&
	grep "\"max_cores\": 4321" view_queue2.out
'

test_expect_success 'list-queues: max_nodes/cores properties show up' '
	flux account list-queues > list_queues1.out &&
	grep "max_nodes" list_queues1.out &&
	grep "max_cores" list_queues1.out
'

test_expect_success 'list-queues: max_nodes/cores can be specified in --fields' '
	flux account list-queues \
		--fields=queue,max_nodes,max_cores > list_queues2.out &&
	grep "queue | max_nodes | max_cores" list_queues2.out &&
	grep "q1    | unlimited | unlimited" list_queues2.out &&
	grep "q2    | 8765      | 4321" list_queues2.out
'

test_expect_success 'edit-queue: max_nodes/cores properties can be edited' '
	flux account edit-queue q1 --max-nodes=9999 --max-cores=9999 &&
	flux account view-queue q1 > edit_queue1.out &&
	grep "\"max_nodes\": 9999" edit_queue1.out &&
	grep "\"max_cores\": 9999" edit_queue1.out
'

test_expect_success 'edit-queue: max_nodes/cores properties can be reset' '
	flux account edit-queue q1 --max-nodes=-1 --max-cores=-1 &&
	flux account view-queue q1 > edit_queue2.out &&
	grep "\"max_nodes\": \"unlimited\"" edit_queue2.out &&
	grep "\"max_cores\": \"unlimited\"" edit_queue2.out
'

test_expect_success 'edit-queue: invalid max_nodes/cores values are rejected' '
	test_must_fail flux account edit-queue \
		q1 --max-nodes=-2 > bad_value1.out 2>&1 &&
	grep "value must be a non-negative integer or -1 to reset to default" bad_value1.out &&
	test_must_fail flux account edit-queue \
		q1 --max-cores=-2 > bad_value2.out 2>&1 &&
	grep "value must be a non-negative integer or -1 to reset to default" bad_value2.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
