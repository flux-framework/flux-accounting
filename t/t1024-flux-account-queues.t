#!/bin/bash

test_description='test flux-account commands that deal with queues'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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
	grep "standby | 0        | 100              | unlimited" standby_parsable.out
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
	flux account add-queue queue_1 &&
	flux account view-queue queue_1 > new_queue.out &&
	jq -e ".[0] == {queue: \"queue_1\", priority: 0,
		max_running_jobs: 100, max_sched_jobs: \"unlimited\",
		max_sched_nodes_per_assoc: \"unlimited\",
		max_sched_cores_per_assoc: \"unlimited\",
		max_nodes: \"unlimited\", max_cores: \"unlimited\"}" <new_queue.out
'

test_expect_success 'add another queue with some optional args' '
	flux account add-queue queue_2 \
		--priority=1 \
		--max-running-jobs=10 \
		--max-sched-jobs=120 \
		--max-sched-nodes-per-assoc=1234 &&
	flux account view-queue queue_2 > new_queue2.out &&
	jq -e ".[0] | .queue == \"queue_2\" and .priority == 1 and
		.max_running_jobs == 10 and .max_sched_jobs == 120 and
		.max_sched_nodes_per_assoc == 1234" <new_queue2.out
'

test_expect_success 'edit some queue information' '
	flux account edit-queue queue_1 --max-running-jobs 50 &&
	flux account view-queue queue_1 > edited_max_jobs.out &&
	jq -e ".[0].max_running_jobs == 50" <edited_max_jobs.out
'

test_expect_success 'edit multiple columns for one queue' '
	flux account edit-queue queue_1 \
		--priority 1 \
		--max-running-jobs 128 \
		--max-sched-jobs 120 \
		--max-sched-nodes-per-assoc 1234 &&
	flux account view-queue queue_1 > edited_queue_multiple.out &&
	jq -e ".[0] | .priority == 1 and .max_running_jobs == 128 and
		.max_sched_jobs == 120 and .max_sched_nodes_per_assoc == 1234" \
		<edited_queue_multiple.out
'

test_expect_success 'reset a queue limit' '
	flux account edit-queue queue_1 --max-running-jobs -1 &&
	flux account view-queue queue_1 > reset_limit.out &&
	jq -e ".[0].max_running_jobs == 100" <reset_limit.out
'

test_expect_success 'trying to view a queue that does not exist should raise a ValueError' '
	test_must_fail flux account view-queue foo > queue_nonexistent.out 2>&1 &&
	grep "queue foo not found in queue_table" queue_nonexistent.out
'

test_expect_success 'call list-queues' '
	flux account list-queues > list_queues.out &&
	grep "standby" list_queues.out &&
	grep "expedite" list_queues.out &&
	grep "queue_1" list_queues.out &&
	grep "queue_2" list_queues.out
'

test_expect_success 'call list-queues and customize output' '
	flux account list-queues --fields=queue,priority --json > list_queues_json.out &&
	grep "\"queue\": \"standby\"" list_queues_json.out &&
	grep "\"queue\": \"expedite\"" list_queues_json.out &&
	grep "\"queue\": \"queue_1\"" list_queues_json.out &&
	grep "\"queue\": \"queue_2\"" list_queues_json.out
'

test_expect_success 'call list-queues with a format string' '
	flux account list-queues \
		-o "{queue:<8}||{max_running_jobs:<16}" > format_string.out &&
	grep "queue   ||max_running_jobs" format_string.out &&
	grep "standby ||100" format_string.out
'

test_expect_success 'remove a queue that is referenced by at least one association' '
	flux account edit-user user5014 --queues="queue_2" &&
	flux account delete-queue queue_2 > warning_message.out &&
	grep "WARNING: user(s) in the association_table still reference this queue." warning_message.out
'

test_expect_success 'add-queue RPC with old fields still adds the queue' '
	cat <<-EOF >outdated_fields.py
	import flux
	import json

	data = { "queue" : "queue_foo", "max_time_per_job" : 60 }
	flux.Flux().rpc("accounting.add_queue", json.dumps(data)).get()
	EOF
	flux python outdated_fields.py &&
	flux account view-queue queue_foo > queue_foo.out &&
	grep "\"queue\": \"queue_foo\"" queue_foo.out &&
	grep "\"priority\": 0" queue_foo.out
'

test_expect_success 'edit-queue RPC with old fields ignores the old fields' '
	cat <<-EOF >outdated_fields.py
	import flux
	import json

	data = { "queue" : "queue_foo", "max_time_per_job" : 60, "priority" : 1234 }
	flux.Flux().rpc("accounting.edit_queue", json.dumps(data)).get()
	EOF
	flux python outdated_fields.py &&
	flux account view-queue queue_foo > queue_foo_edited.out &&
	grep "\"queue\": \"queue_foo\"" queue_foo_edited.out &&
	grep "\"priority\": 1234" queue_foo_edited.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
