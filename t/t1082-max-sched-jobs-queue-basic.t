#!/bin/bash

test_description='test managing the max-sched-jobs property'

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

test_expect_success 'view-queue: default max_sched_jobs value shows up in view-queue' '
	flux account add-queue q1 &&
	flux account view-queue q1 > view_queue1.out &&
	grep "\"max_sched_jobs\": \"unlimited\"" view_queue1.out
'

test_expect_success 'view-queue: configured max_sched_jobs value shows up in view-queue' '
	flux account add-queue q2 --max-sched-jobs=1234 &&
	flux account view-queue q2 > view_queue2.out &&
	grep "\"max_sched_jobs\": 1234" view_queue2.out
'

test_expect_success 'view-queue: default max_sched_jobs value shows up in --parsable option' '
	flux account view-queue q1 --parsable > view_queue3.out &&
	grep "max_sched_jobs" view_queue3.out &&
	grep "unlimited" view_queue3.out
'

test_expect_success 'view-queue: configured max_sched_jobs value shows up in --parsable option' '
	flux account view-queue q2 --parsable > view_queue4.out &&
	grep "max_sched_jobs" view_queue4.out &&
	grep "1234" view_queue4.out
'

test_expect_success 'view-queue: max_sched_jobs property can be passed in format string' '
	flux account view-queue q1 -o "{queue:<8} | {max_sched_jobs:<15}" > view_queue5.out &&
	grep "queue    | max_sched_jobs" view_queue5.out &&
	grep "q1       | 2147483647" view_queue5.out
'

test_expect_success 'list-queues: max_sched_jobs property shows up under list-queues' '
	flux account list-queues > list_queues1.out &&
	grep "max_sched_jobs" list_queues1.out &&
	grep "unlimited" list_queues1.out &&
	grep "1234" list_queues1.out
'

test_expect_success 'list-queues: max_sched_jobs property can be specified in --fields' '
	flux account list-queues --fields=queue,max_sched_jobs > list_queues2.out &&
	grep "queue | max_sched_jobs" list_queues2.out &&
	grep "q1    | unlimited" list_queues2.out &&
	grep "q2    | 1234" list_queues2.out
'

test_expect_success 'edit-queue: max_sched_jobs property can be edited' '
	flux account edit-queue q1 --max-sched-jobs=9999 &&
	flux account view-queue q1 > edit_queue1.out &&
	grep "\"max_sched_jobs\": 9999" edit_queue1.out
'

test_expect_success 'edit-queue: max_sched_jobs property can be reset' '
	flux account edit-queue q1 --max-sched-jobs=-1 &&
	flux account view-queue q1 > edit_queue2.out &&
	grep "\"max_sched_jobs\": \"unlimited\"" edit_queue2.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
