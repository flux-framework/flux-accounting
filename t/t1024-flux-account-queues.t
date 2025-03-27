#!/bin/bash

test_description='test flux-account commands that deal with queues'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=root D 1 &&
	flux account add-bank --parent-bank=D E 1
	flux account add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user5011 --userid=5011 --bank=A &&
	flux account add-user --username=user5012 --userid=5012 --bank=A &&
	flux account add-user --username=user5013 --userid=5013 --bank=B &&
	flux account add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue standby --priority=0 &&
	flux account add-queue expedite --priority=10000 &&
	flux account add-queue special --priority=99999
'

test_expect_success 'view some queue information' '
	flux account view-queue standby > standby.out &&
	grep "\"queue\": \"standby\"" standby.out &&
	grep "\"priority\": 0" standby.out
'

test_expect_success 'view some queue information with --parsable' '
	flux account view-queue standby --parsable > standby_parsable.out &&
	grep "standby | 1                 | 1                 | 60               | 0" standby_parsable.out
'

test_expect_success 'call view-queue with a format string' '
	flux account view-queue standby -o "{queue:<8} || {priority:<12}" > standby_format_string.out &&
	grep "queue    || priority" standby_format_string.out &&
	grep "standby  || 0" standby_format_string.out
'

test_expect_success 'add a queue to an existing user account' '
	flux account edit-user user5011 --queue="expedite"
'

test_expect_success 'trying to add a non-existent queue to a user account should raise a ValueError' '
	test_must_fail flux account edit-user user5011 --queue="foo" > bad_queue.out 2>&1 &&
	grep "queue foo does not exist in queue_table" bad_queue.out
'

test_expect_success 'trying to add a user with a non-existent queue should also return an error' '
	test_must_fail flux account add-user --username=user5015 --bank=A --queue="foo" > bad_queue2.out 2>&1 &&
	grep "queue foo does not exist in queue_table" bad_queue2.out
'

test_expect_success 'add multiple queues to an existing user account' '
	flux account edit-user user5012 --queue="expedite,standby" &&
	flux account view-user user5012 > user5012.out &&
	grep "expedite,standby" user5012.out
'

test_expect_success 'edit a queue priority' '
	flux account edit-queue expedite --priority=20000 &&
	flux account view-queue expedite > edited_queue.out &&
	grep "20000" edited_queue.out
'

test_expect_success 'remove a queue' '
	flux account delete-queue special &&
	test_must_fail flux account view-queue special > deleted_queue.out 2>&1 &&
	grep "queue special not found in queue_table" deleted_queue.out
'

test_expect_success 'add a queue with no optional args to the queue_table' '
	flux account add-queue queue_1
	flux account view-queue queue_1 > new_queue.out &&
	grep -w "queue_1\|1\|1\|60\|0" new_queue.out
'

test_expect_success 'add another queue with some optional args' '
	flux account add-queue queue_2 --min-nodes-per-job=1 --max-nodes-per-job=10 --max-time-per-job=120 &&
	flux account view-queue queue_2 > new_queue2.out &&
	grep -w "queue_1\|1\|10\|120" new_queue2.out
'

test_expect_success 'edit some queue information' '
	flux account edit-queue queue_1 --max-nodes-per-job 100 &&
	flux account view-queue queue_1 > edited_max_nodes.out &&
	grep -w "queue_1\|100" edited_max_nodes.out
'

test_expect_success 'edit multiple columns for one queue' '
	flux account edit-queue queue_1 --min-nodes-per-job 1 --max-nodes-per-job 128 --max-time-per-job 120 &&
	flux account view-queue queue_1 > edited_queue_multiple.out &&
	grep -w "queue_1\|1\|128\|120" edited_queue_multiple.out
'

test_expect_success 'reset a queue limit' '
	flux account edit-queue queue_1 --max-nodes-per-job -1 &&
	flux account view-queue queue_1 > reset_limit.out &&
	grep -w "queue_1\|1\|1\|120\|0" reset_limit.out
'

test_expect_success 'trying to view a queue that does not exist should raise a ValueError' '
	test_must_fail flux account view-queue foo > queue_nonexistent.out 2>&1 &&
	grep "queue foo not found in queue_table" queue_nonexistent.out
'

test_expect_success 'call list-queues' '
	flux account list-queues > list_queues.out &&
	grep "\"queue\": \"standby\"" list_queues.out &&
	grep "\"queue\": \"expedite\"" list_queues.out &&
	grep "\"queue\": \"queue_1\"" list_queues.out &&
	grep "\"queue\": \"queue_2\"" list_queues.out
'

test_expect_success 'call list-queues and customize output' '
	flux account list-queues --fields=queue,priority --table > list_queues_table.out &&
	grep "standby  | 0" list_queues_table.out &&
	grep "expedite | 20000" list_queues_table.out &&
	grep "queue_1  | 0" list_queues_table.out &&
	grep "queue_2  | 0" list_queues_table.out
'

test_expect_success 'call list-queues with a format string' '
	flux account list-queues \
		-o "{queue:<8}||{max_time_per_job:<12}" > format_string.out &&
	grep "queue   ||max_time_per_job" format_string.out &&
	grep "standby ||60" format_string.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
