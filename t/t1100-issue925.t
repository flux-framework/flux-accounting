#!/bin/bash

test_description='test that edit-queue does not reset max-sched-* limits'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add a queue with explicit max-sched-* limits' '
	flux account add-queue myqueue \
		--max-sched-jobs=5 \
		--max-sched-nodes-per-assoc=10 \
		--max-sched-cores-per-assoc=20
'

test_expect_success 'confirm the max-sched-* limits were correctly stored' '
	flux account view-queue myqueue -o \
		"{max_sched_jobs} {max_sched_nodes_per_assoc} {max_sched_cores_per_assoc}" \
		> before.out &&
	grep "5 10 20" before.out
'

test_expect_success 'edit an unrelated property on the queue' '
	flux account edit-queue myqueue --priority=42 &&
	flux account view-queue myqueue -o "{queue},{priority}" > prio.out &&
	grep "myqueue,42" prio.out
'

test_expect_success 'max-sched-* limits are not reset by the edit' '
	flux account view-queue myqueue -o \
		"{max_sched_jobs} {max_sched_nodes_per_assoc} {max_sched_cores_per_assoc}" \
		> after.out &&
	grep "5 10 20" after.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
