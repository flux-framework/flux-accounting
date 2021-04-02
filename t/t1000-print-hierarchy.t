#!/bin/bash

test_description='Test print-hierarchy command'
. `dirname $0`/sharness.sh
PRINT_HIERARCHY=${FLUX_BUILD_DIR}/src/fairness/print_hierarchy/flux-shares
SMALL_NO_TIE=${FLUX_BUILD_DIR}/src/fairness/reader/test/accounting_db_data/small_no_tie.db
SMALL_TIE=${FLUX_BUILD_DIR}/src/fairness/reader/test/accounting_db_data/small_tie.db
SMALL_TIE_ALL=${FLUX_BUILD_DIR}/src/fairness/reader/test/accounting_db_data/small_tie_all.db
OUT_OF_INSERT_ORDER=${FLUX_BUILD_DIR}/src/fairness/reader/test/accounting_db_data/out_of_insert_order.db

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
    ${PRINT_HIERARCHY} -f ${SMALL_NO_TIE} > test_small_no_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_no_tie.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_no_tie.txt test_small_no_tie.txt
'

test_expect_success 'create hierarchy output from C++ - small_tie.db' '
    ${PRINT_HIERARCHY} -f ${SMALL_TIE} > test_small_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_tie.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_tie.txt test_small_tie.txt
'

test_expect_success 'create hierarchy output from C++ - small_tie_all.db' '
    ${PRINT_HIERARCHY} -f ${SMALL_TIE_ALL} > test_small_tie_all.txt
'

test_expect_success 'compare hierarchy outputs - small_tie_all.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_tie_all.txt test_small_tie_all.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_no_tie.db' '
    ${PRINT_HIERARCHY} -P "|" -f ${SMALL_NO_TIE} > test_small_no_tie_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_no_tie.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_no_tie_parsable.txt test_small_no_tie_parsable.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_tie.db' '
    ${PRINT_HIERARCHY} -P "|" -f ${SMALL_TIE} > test_small_tie_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_tie.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_tie_parsable.txt test_small_tie_parsable.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_tie_all.db' '
    ${PRINT_HIERARCHY} -P "|" -f ${SMALL_TIE_ALL} > test_small_tie_all_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_tie_all.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/small_tie_all_parsable.txt test_small_tie_all_parsable.txt
'

test_expect_success 'create custom parsable hierarchy output from C++ - small_tie.db' '
    ${PRINT_HIERARCHY} -P , -f ${SMALL_TIE} > test_custom_small_tie_parsable.txt
'

test_expect_success 'compare custom parsable hierarchy outputs - small_tie_all.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/custom_small_tie_parsable.txt test_custom_small_tie_parsable.txt
'

test_expect_success 'output help message for flux-shares' '
    ${PRINT_HIERARCHY} -h > test_help_message.txt
'

test_expect_success 'compare help message for flux-shares' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/help_message.txt test_help_message.txt
'

test_expect_failure 'output help message for flux-shares when a bad argument is passed in' '
    ${PRINT_HIERARCHY} --bad-arg > test_bad_argument.txt
'

test_expect_success 'compare help message for flux-shares when a bad argument is passed in' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/help_message.txt test_bad_argument.txt
'

test_expect_success 'create hierarchy output from C++ - out_of_insert_order.db' '
    ${PRINT_HIERARCHY} -f ${OUT_OF_INSERT_ORDER} > test_out_of_insert_order.txt
'

test_expect_success 'compare hierarchy outputs - out_of_insert_order.db' '
    test_cmp ${FLUX_BUILD_DIR}/t/expected/out_of_insert_order.txt test_out_of_insert_order.txt
'

test_done
