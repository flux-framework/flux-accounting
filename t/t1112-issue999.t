#!/bin/bash

test_description='test reprioritize uses each job queue priority'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

# print the value of the most recent priority event in a job's eventlog
last_priority () {
	flux job eventlog -f json "$1" \
		| jq -s "[.[] | select(.name == \"priority\")] | last | .context.priority"
}

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'add banks, queues, and association to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-queue low --priority=1 &&
	flux account add-queue high --priority=1000 &&
	flux account add-user \
		--username=user1 \
		--userid=50001 \
		--bank=A \
		--queues=low,high
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'configure and stop queues so jobs stay pending' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.low]
	[queues.high]
	EOT
	flux config reload &&
	flux queue stop --all
'

test_expect_success 'high-queue job keeps priority after later low submit' '
	high_after_submit=$(flux python ${SUBMIT_AS} 50001 \
		--queue=high sleep 30) &&
	flux job wait-event -t 5 ${high_after_submit} priority &&
	test "$(last_priority ${high_after_submit})" = "10050000" &&
	low_after_submit=$(flux python ${SUBMIT_AS} 50001 \
		--queue=low sleep 30) &&
	flux job wait-event -t 5 ${low_after_submit} priority &&
	flux account-priority-update -p ${DB_PATH} &&
	test "$(last_priority ${high_after_submit})" = "10050000"
'

test_expect_success 'high-queue job keeps priority after low move' '
	move_high=$(flux python ${SUBMIT_AS} 50001 --queue=high sleep 30) &&
	flux job wait-event -t 5 ${move_high} priority &&
	move_low=$(flux python ${SUBMIT_AS} 50001 --queue=high sleep 30) &&
	flux job wait-event -t 5 ${move_low} priority &&
	flux update ${move_low} queue=low &&
	flux job wait-event -f json -t 5 --count=2 ${move_low} priority \
		| jq ".context.priority" > move_low.test &&
	test "$(cat move_low.test)" = "60000" &&
	flux account-priority-update -p ${DB_PATH} &&
	test "$(last_priority ${move_high})" = "10050000"
'

# A pending job keeps the priority of the queue it was submitted to even after
# the association loses access to that queue; queue access is only enforced
# when a job is submitted or updated.
test_expect_success 'high-queue job keeps priority after access change' '
	access_high=$(flux python ${SUBMIT_AS} 50001 --queue=high sleep 30) &&
	flux job wait-event -t 5 ${access_high} priority &&
	access_low=$(flux python ${SUBMIT_AS} 50001 --queue=low sleep 30) &&
	flux job wait-event -t 5 ${access_low} priority &&
	flux account edit-user user1 --bank=A --queues=low &&
	flux account-priority-update -p ${DB_PATH} &&
	test "$(last_priority ${access_high})" = "10050000"
'

# Every pending job in the "high" queue must be reprioritized using the new
# queue priority (1000 -> 2000). A priority event is posted with or without
# the fix, so wait for it and check its value
test_expect_success 'editing queue priority reprioritizes pending jobs' '
	flux account edit-queue high --priority=2000 &&
	flux account-priority-update -p ${DB_PATH} &&
	flux job wait-event -f json -t 5 --count=2 ${high_after_submit} priority \
		| jq ".context.priority" > high_after_edit.test &&
	test "$(cat high_after_edit.test)" = "20050000" &&
	flux job wait-event -f json -t 5 --count=2 ${move_high} priority \
		| jq ".context.priority" > move_high_after_edit.test &&
	test "$(cat move_high_after_edit.test)" = "20050000"
'

test_expect_success 'cancel pending jobs' '
	flux cancel ${high_after_submit} ${low_after_submit} \
		${move_high} ${move_low} ${access_high} ${access_low}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
