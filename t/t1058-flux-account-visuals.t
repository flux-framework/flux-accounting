#!/bin/bash

test_description='test visualizing flux-accounting numerical data'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
UPDATE_USAGE_COL=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

mkdir -p config

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'call show-usage with no data' '
	flux account show-usage associations > no_association_data.out &&
	grep "no data to display" no_association_data.out &&
	flux account show-usage banks > no_bank_data.out &&
	grep "no data to display" no_bank_data.out
'

test_expect_success 'call show-usage --help' '
	flux account show-usage --help
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'add some associations' '
	flux account add-user --username=user1 --bank=A &&
	flux account add-user --username=user2 --bank=A &&
	flux account add-user --username=user3 --bank=B &&
	flux account add-user --username=user4 --bank=B &&
	flux account add-user --username=user5 --bank=C
'

test_expect_success 'edit job usage values for every association' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user1 5 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user2 14 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user3 7 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user4 45 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user5 23
'

test_expect_success 'update usage for entire flux-accounting DB hierarchy' '
	flux account-update-usage -p ${DB_PATH}
'

test_expect_success 'call show-usage for associations' '
	flux account show-usage associations > associations.out &&
	grep "user4" associations.out | grep 45 &&
	grep "user5" associations.out | grep 23 &&
	grep "user2" associations.out | grep 14 &&
	grep "user3" associations.out | grep 7 &&
	grep "user1" associations.out | grep 5
'

test_expect_success 'call show-usage for banks' '
	flux account show-usage banks > banks.out &&
	grep "B" banks.out | grep 52 &&
	grep "C" banks.out | grep 23 &&
	grep "A" banks.out | grep 19
'

test_expect_success 'call show-usage for associations with --limit' '
	flux account show-usage associations --limit=1 > associations_limited.out &&
	grep "user4" associations_limited.out | grep 45 
'

test_expect_success 'call show-usage for banks with --limit' '
	flux account show-usage banks --limit=1 > banks_limited.out &&
	grep "B" banks_limited.out | grep 52
'

test_expect_success 'call show-usage with a bad table name' '
	test_must_fail flux account show-usage foo > error.out 2>&1 &&
	cat error.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
