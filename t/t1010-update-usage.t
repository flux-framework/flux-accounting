#!/bin/bash

test_description='Test flux account update-usage command with user and job data'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
CREATE_TEST_DB=${SHARNESS_TEST_SRCDIR}/scripts/create_test_db.py
UPDATE_USAGE_COL=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py
CREATE_JOB_ARCHIVE=${SHARNESS_TEST_SRCDIR}/scripts/create_job_archive_db.py

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
	flux account add-bank --parent-bank=root account1 1 &&
	flux account add-bank --parent-bank=root account2 1 &&
	flux account add-bank --parent-bank=root account3 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=5011 --userid=5011 --bank=account1 --shares=1 &&
	flux account add-user --username=5012 --userid=5012 --bank=account1 --shares=1 &&
	flux account add-user --username=5013 --userid=5013 --bank=account1 --shares=1 &&
	flux account add-user --username=5021 --userid=5021 --bank=account2 --shares=1 &&
	flux account add-user --username=5022 --userid=5022 --bank=account2 --shares=1 &&
	flux account add-user --username=5031 --userid=5031 --bank=account3 --shares=1 &&
	flux account add-user --username=5032 --userid=5032 --bank=account3 --shares=1
'

test_expect_success 'create sample job-archive DB' '
	flux python ${CREATE_JOB_ARCHIVE}
'

test_expect_success 'update-usage raises a usage error when passing a bad type for priority-decay-half-life' '
	test_must_fail flux account update-usage job-archive.sqlite \
		--priority-decay-half-life foo > bad_arg.out 2>&1 &&
	test_debug "cat bad_arg.out" &&
	grep "flux-account.py update-usage: error: argument --priority-decay-half-life: invalid int value:" bad_arg.out
'

test_expect_success 'create & compare hierarchy output from FluxAccountingTest.db: pre-usage update' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > pre_update.test &&
	test_cmp ${SHARNESS_TEST_SRCDIR}/expected/job_usage/pre_update.expected pre_update.test
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account update-usage job-archive.sqlite &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'create & compare hierarchy output from FluxAccountingTest.db: post-usage update 1' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > post_update1.test &&
	test_cmp ${SHARNESS_TEST_SRCDIR}/expected/job_usage/post_update2.expected post_update1.test
'

test_expect_success 'run update-usage and update-fshare commands with an optional arg' '
	flux account update-usage job-archive.sqlite --priority-decay-half-life 1 &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'create & compare hierarchy output from FluxAccountingTest.db: post-usage update 2' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > post_update2.test &&
	test_cmp ${SHARNESS_TEST_SRCDIR}/expected/job_usage/post_update2.expected post_update2.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
