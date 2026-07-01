#!/bin/bash

test_description='test incremental queue operations for associations'

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

test_expect_success 'add a bank to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association to the DB' '
	flux account add-user --username=user1 --userid=5001 --bank=A
'

test_expect_success 'add queues to the DB' '
	flux account add-queue queue_1 &&
	flux account add-queue queue_2 &&
	flux account add-queue queue_3
'

test_expect_success 'add queue_1 to user1' '
	flux account edit-user user1 --add-queue=queue_1 &&
	flux account view-user user1 > user1_queue1.out &&
	grep "\"queues\": \"queue_1\"" user1_queue1.out
'

test_expect_success 'add queue_2 to user1' '
	flux account edit-user user1 --add-queue=queue_2 &&
	flux account view-user user1 > user1_queue2.out &&
	grep "\"queues\": \"queue_1,queue_2\"" user1_queue2.out
'

test_expect_success 'adding duplicate queue will not affect existing list' '
	flux account edit-user user1 --add-queue=queue_1 &&
	flux account view-user user1 > no_duplicates.out &&
	grep "\"queues\": \"queue_1,queue_2\"" no_duplicates.out
'

test_expect_success 'delete queue_1 from user1' '
	flux account edit-user user1 --delete-queue=queue_1 &&
	flux account view-user user1 > user1_deleted_queue1.out &&
	grep "\"queues\": \"queue_2\"" user1_deleted_queue1.out
'

test_expect_success 'deleting non-existent queue will not affect existing list' '
	flux account edit-user user1 --delete-queue=queue_3 &&
	flux account view-user user1 > deleted_queue2.out
	grep "\"queues\": \"queue_2\"" deleted_queue2.out
'

test_expect_success 'cannot use --queues with --add-queue' '
	test_must_fail flux account edit-user user1 \
		--queues=queue_1,queue_2 --add-queue=queue_3 > conflict.out 2>&1 &&
	grep "cannot specify --queues with --add-queue" conflict.out
'

test_expect_success 'cannot use --queues with --delete-queue' '
	test_must_fail flux account edit-user user1 \
		--queues=queue_1,queue_2 --delete-queue=queue_3 > conflict2.out 2>&1 &&
	grep "cannot specify --queues with --add-queue" conflict2.out
'

test_expect_success 'adding non-existent queue should fail' '
	test_must_fail flux account edit-user user1 \
		--add-queue=nonexistent_queue > bad_queue.out 2>&1 &&
	grep "does not exist in queue_table" bad_queue.out
'

test_expect_success 'can still use --queues for full replacement' '
	flux account edit-user user1 --queues=queue_1,queue_3 &&
	flux account view-user user1 > user1_replaced_queues.out &&
	grep "\"queues\": \"queue_1,queue_3\"" user1_replaced_queues.out
'

test_expect_success 'add queue_2 back using --add-queue' '
	flux account edit-user user1 --add-queue=queue_2 &&
	flux account view-user user1 > user1_three_queues.out &&
	grep "\"queues\": \"queue_1,queue_3,queue_2\"" user1_three_queues.out
'

test_expect_success 'add another bank so user can belong to more than one bank' '
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-user --username=user1 --bank=B
'

test_expect_success 'add queue_1 to user1/B association' '
	flux account edit-user user1 --bank=B --add-queue=queue_1 &&
	flux account view-user user1 > user1_B_queue2.out &&
	grep "\"queues\": \"queue_1\"" user1_B_queue2.out
'

test_expect_success 'add queue_2 across all of their banks' '
	flux account edit-user user1 --add-queue=queue_2 &&
	flux account view-user user1 > user1_both_banks.out &&
	grep "\"queues\": \"queue_1,queue_2\"" user1_both_banks.out &&
	grep "\"queues\": \"queue_1,queue_3,queue_2\"" user1_both_banks.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
