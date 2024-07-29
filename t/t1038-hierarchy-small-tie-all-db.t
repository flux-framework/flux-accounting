#!/bin/bash

test_description='test printing the DB hierarchy with all job usage ties'

. `dirname $0`/sharness.sh
SMALL_TIE_ALL=$(pwd)/small_tie_all.db

EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/print_hierarchy
UPDATE_USAGE=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create small_no_tie flux-accounting DB' '
	flux account -p ${SMALL_TIE_ALL} create-db
'

test_expect_success 'start flux-accounting service on small_no_tie DB' '
	flux account-service -p ${SMALL_TIE_ALL} -t
'

test_expect_success 'add users/banks to DB' '
	flux account add-bank root 1000 &&
	flux account add-bank --parent-bank root account1 1000 &&
	flux account add-bank --parent-bank root account2 100 &&
	flux account add-bank --parent-bank root account3 10000 &&
	flux account add-user --username leaf.1.1 --bank account1 --shares 10000 &&
	flux account add-user --username leaf.1.2 --bank account1 --shares 1000 &&
	flux account add-user --username leaf.1.3 --bank account1 --shares 100000 &&
	flux account add-user --username leaf.2.1 --bank account2 --shares 10000 &&
	flux account add-user --username leaf.2.2 --bank account2 --shares 1000 &&
	flux account add-user --username leaf.2.3 --bank account2 --shares 100000 &&
	flux account add-user --username leaf.3.1 --bank account3 --shares 10000 &&
	flux account add-user --username leaf.3.2 --bank account3 --shares 1000 &&
	flux account add-user --username leaf.3.3 --bank account3 --shares 100000
'

test_expect_success 'update usage and fair-share for the users/banks' '
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.1.1 100 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.1.2 10 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.1.3 10 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.2.1 10 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.2.2 1 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.2.3 1 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.3.1 1000 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.3.2 100 &&
	flux python ${UPDATE_USAGE} ${SMALL_TIE_ALL} leaf.3.3 100 &&
	flux account update-usage &&
	flux account-update-fshare -p ${SMALL_TIE_ALL}
'

test_expect_success 'view database hierarchy' '
	flux account view-bank -t root > small_tie_all.test &&
	test_cmp ${EXPECTED_FILES}/small_tie_all.txt small_tie_all.test
'

test_expect_success 'view database hierarchy in a parseable format' '
	flux account view-bank -P root > small_tie_all_parsable.test &&
	test_cmp ${EXPECTED_FILES}/small_tie_all_parsable.txt small_tie_all_parsable.test
'

test_expect_success 'remove flux-accounting DB' '
	rm ${SMALL_TIE_ALL}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
