#!/bin/bash

test_description='Test update-fshare command with user and job data'

. `dirname $0`/sharness.sh

EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/update_fshare
CREATE_TEST_DB=${SHARNESS_TEST_SRCDIR}/scripts/create_test_db.py
UPDATE_USAGE_COL=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'trying to run update-fshare with bad DBPATH should return an error' '
	test_must_fail flux account-update-fshare -p foo.db > failure.out 2>&1 &&
	test_debug "cat failure.out" &&
	grep "error opening DB: unable to open database file" failure.out
'

test_expect_success 'trying to run update-usage with bad DBPATH should also return an error' '
	test_must_fail flux account-update-usage -p foo.db > failure.out 2>&1 &&
	test_debug "cat failure.out" &&
	grep "error opening DB: unable to open database file foo.db" failure.out
'

test_expect_success 'create t_small_no_tie.db' '
	flux python ${CREATE_TEST_DB} $(pwd)/t_small_no_tie.db
'

test_expect_success 'start flux-accounting service on small_no_tie DB' '
	flux account-service -p $(pwd)/t_small_no_tie.db -t
'

test_expect_success 'create hierarchy output from t_small_no_tie.db' '
	flux account view-bank root -t
'

test_expect_success 'run update fshare script - small_no_tie.db' '
	flux account-update-usage -p $(pwd)/t_small_no_tie.db &&
	flux account-update-fshare -p $(pwd)/t_small_no_tie.db
'

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
	flux account view-bank root -t > pre_fshare_update.test
'

test_expect_success 'compare hierarchy outputs' '
	test_cmp ${EXPECTED_FILES}/pre_fshare_update.expected pre_fshare_update.test
'

test_expect_success 'update usage column in t_small_no_tie.db' '
	flux python ${UPDATE_USAGE_COL} $(pwd)/t_small_no_tie.db leaf.2.1 55
'

test_expect_success 'run update fshare script - small_no_tie.db' '
	flux account-update-usage -p $(pwd)/t_small_no_tie.db &&
	flux account-update-fshare -p $(pwd)/t_small_no_tie.db
'

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
	flux account view-bank root -t > post_fshare_update.test
'

test_expect_success 'compare hierarchy outputs' '
	test_cmp ${EXPECTED_FILES}/post_fshare_update.expected post_fshare_update.test
'

test_expect_success 'delete t_small_no_tie.db' '
	rm $(pwd)/t_small_no_tie.db
'

test_done
