#!/bin/bash

test_description='Test print-hierarchy command'
. `dirname $0`/sharness.sh
PRINT_HIERARCHY=${FLUX_BUILD_DIR}/src/fairness/print_hierarchy/flux-shares
UPDATE_FSHARE=${FLUX_BUILD_DIR}/src/cmd/flux-update-fshare

CREATE_TEST_DB=${FLUX_BUILD_DIR}/t/scripts/create_test_db.py
UPDATE_USAGE_COL=${FLUX_BUILD_DIR}/t/scripts/update_usage_column.py

T_SMALL_NO_TIE=${FLUX_BUILD_DIR}/t/expected/t_small_no_tie.db

test_expect_success 'trying to run update-fshare with bad DBPATH should return an error' '
	test_must_fail ${UPDATE_FSHARE} -f foo.db > failure.out 2>&1 &&
	test_debug "cat failure.out" &&
	grep "error opening DB: unable to open database file" failure.out
'

test_expect_success 'create t_small_no_tie.db' '
	flux python ${CREATE_TEST_DB} ${FLUX_BUILD_DIR}/t/expected/t_small_no_tie.db
'

test_expect_success 'create hierarchy output from t_small_no_tie.db' '
	${PRINT_HIERARCHY} -f ${T_SMALL_NO_TIE}
'

test_expect_success 'run update fshare script - small_no_tie.db' '
	${UPDATE_FSHARE} -f ${T_SMALL_NO_TIE}
'

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
	${PRINT_HIERARCHY} -f ${T_SMALL_NO_TIE} > pre_fshare_update.test
'

test_expect_success 'compare hierarchy outputs' '
	test_cmp ${FLUX_BUILD_DIR}/t/expected/pre_fshare_update.expected pre_fshare_update.test
'

test_expect_success 'update usage column in t_small_no_tie.db' '
	flux python ${UPDATE_USAGE_COL} ${T_SMALL_NO_TIE} leaf.2.1 55
'

test_expect_success 'run update fshare script - small_no_tie.db' '
	${UPDATE_FSHARE} -f ${T_SMALL_NO_TIE}
'

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
	${PRINT_HIERARCHY} -f ${T_SMALL_NO_TIE} > post_fshare_update.test
'

test_expect_success 'compare hierarchy outputs' '
	test_cmp ${FLUX_BUILD_DIR}/t/expected/post_fshare_update.expected post_fshare_update.test
'

test_expect_success 'delete t_small_no_tie.db' '
	rm ${T_SMALL_NO_TIE}
'

test_done
