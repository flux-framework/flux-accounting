#!/bin/bash

test_description='test periodic usage decay after repairing an association userid'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
USAGE_HELPER=${SHARNESS_TEST_SRCDIR}/scripts/t1116/issue1025_usage.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

# Drive the full usage updater with fixed timestamps, while exercising userid
# edits and synchronization through the accounting service. No jobs need to
# run and no wall-clock delay is needed to cross a half-life boundary.
test_expect_success 'create periodic database with four 100-second bins' '
	flux account -p ${DB_PATH} create-db --decay-method=periodic \
		--priority-decay-half-life=100s --priority-usage-reset-period=400s
'

test_expect_success 'start accounting service and add association' '
	flux account-service -p ${DB_PATH} -t &&
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=1001 --bank=A
'

test_expect_success 'seed history and rotate before changing userid' '
	flux python ${USAGE_HELPER} ${DB_PATH} seed &&
	flux python ${USAGE_HELPER} ${DB_PATH} update 1150 &&
	flux python ${USAGE_HELPER} ${DB_PATH} snapshot >before.out &&
	cat >before.expected <<-EOF &&
	{"periods": [0.0, 500.0, 250.0, 0.0], "job_usage": 750.0}
	EOF
	test_cmp before.expected before.out
'

test_expect_success 'edit-user --userid updates usage-factor userid' '
	flux account edit-user user1 --userid=2002 &&
	flux python ${USAGE_HELPER} ${DB_PATH} userids >userids.out &&
	echo "[2002, 2002]" >userids.expected &&
	test_cmp userids.expected userids.out
'

test_expect_success 'sync-userids leaves edited userids unchanged' '
	flux account sync-userids &&
	flux python ${USAGE_HELPER} ${DB_PATH} userids >synced.out &&
	test_cmp userids.expected synced.out
'

test_expect_success 'history still rotates and decays after userid repair' '
	flux python ${USAGE_HELPER} ${DB_PATH} update 1250 &&
	flux python ${USAGE_HELPER} ${DB_PATH} snapshot >after.out &&
	cat >after.expected <<-EOF &&
	{"periods": [0.0, 0.0, 250.0, 125.0], "job_usage": 375.0}
	EOF
	test_cmp after.expected after.out
'

test_expect_success 'same-period job adds only its usage to decayed history' '
	flux python ${USAGE_HELPER} ${DB_PATH} add-job &&
	flux python ${USAGE_HELPER} ${DB_PATH} update 1275 &&
	flux python ${USAGE_HELPER} ${DB_PATH} snapshot >job.out &&
	cat >job.expected <<-EOF &&
	{"periods": [15.0, 0.0, 250.0, 125.0], "job_usage": 390.0}
	EOF
	test_cmp job.expected job.out
'

test_expect_success 'shut down accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
