#!/bin/bash

test_description='Test print-hierarchy command'

. `dirname $0`/sharness.sh

EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/print_hierarchy
SMALL_NO_TIE=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/small_no_tie.db
SMALL_TIE=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/small_tie.db
SMALL_TIE_ALL=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/small_tie_all.db
OUT_OF_INSERT_ORDER=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/out_of_insert_order.db
DB_PATH=$(pwd)/FluxAccountingTestHierarchy.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
    flux account -p $(pwd)/FluxAccountingTestHierarchy.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
    flux account-shares -p ${SMALL_NO_TIE} > test_small_no_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_no_tie.db' '
    test_cmp ${EXPECTED_FILES}/small_no_tie.txt test_small_no_tie.txt
'

test_expect_success 'create hierarchy output from C++ - small_tie.db' '
    flux account-shares -p ${SMALL_TIE} > test_small_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_tie.db' '
    test_cmp ${EXPECTED_FILES}/small_tie.txt test_small_tie.txt
'

test_expect_success 'create hierarchy output from C++ - small_tie_all.db' '
    flux account-shares -p ${SMALL_TIE_ALL} > test_small_tie_all.txt
'

test_expect_success 'compare hierarchy outputs - small_tie_all.db' '
    test_cmp ${EXPECTED_FILES}/small_tie_all.txt test_small_tie_all.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_no_tie.db' '
    flux account-shares -P "|" -p ${SMALL_NO_TIE} > test_small_no_tie_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_no_tie.db' '
    test_cmp ${EXPECTED_FILES}/small_no_tie_parsable.txt test_small_no_tie_parsable.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_tie.db' '
    flux account-shares -P "|" -p ${SMALL_TIE} > test_small_tie_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_tie.db' '
    test_cmp ${EXPECTED_FILES}/small_tie_parsable.txt test_small_tie_parsable.txt
'

test_expect_success 'create parsable hierarchy output from C++ - small_tie_all.db' '
    flux account-shares -P "|" -p ${SMALL_TIE_ALL} > test_small_tie_all_parsable.txt
'

test_expect_success 'compare parsable hierarchy outputs - small_tie_all.db' '
    test_cmp ${EXPECTED_FILES}/small_tie_all_parsable.txt test_small_tie_all_parsable.txt
'

test_expect_success 'create custom parsable hierarchy output from C++ - small_tie.db' '
    flux account-shares -P , -p ${SMALL_TIE} > test_custom_small_tie_parsable.txt
'

test_expect_success 'compare custom parsable hierarchy outputs - small_tie_all.db' '
    test_cmp ${EXPECTED_FILES}/custom_small_tie_parsable.txt test_custom_small_tie_parsable.txt
'

test_expect_success 'output help message for flux-shares' '
    flux account-shares -h > test_help_message.txt
'

test_expect_success 'compare help message for flux-shares' '
    test_cmp ${EXPECTED_FILES}/help_message.txt test_help_message.txt
'

test_expect_failure 'output help message for flux-shares when a bad argument is passed in' '
    flux account-shares --bad-arg > test_bad_argument.txt
'

test_expect_success 'compare help message for flux-shares when a bad argument is passed in' '
    test_cmp ${EXPECTED_FILES}/help_message.txt test_bad_argument.txt
'

test_expect_success 'create hierarchy output from C++ - out_of_insert_order.db' '
    flux account-shares -p ${OUT_OF_INSERT_ORDER} > test_out_of_insert_order.txt
'

test_expect_success 'compare hierarchy outputs - out_of_insert_order.db' '
    test_cmp ${EXPECTED_FILES}/out_of_insert_order.txt test_out_of_insert_order.txt
'

test_expect_success 'add some banks and users' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-user --username=user5011 --userid=5011 --bank=A &&
	flux account add-user --username=user5012 --userid=5012 --bank=A &&
	flux account add-user --username=user5013 --userid=5013 --bank=B &&
	flux account add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'print hierarchy' '
    flux account-shares -p ${DB_PATH} > before_delete.test &&
    test_cmp ${EXPECTED_FILES}/before_delete.expected before_delete.test
'

test_expect_success 'delete a user' '
    flux account delete-user user5012 A
'

test_expect_success 'print hierarchy again and check that deleted user does not show up in hierarchy' '
    flux account-shares -p ${DB_PATH} > after_delete.test &&
    test_cmp ${EXPECTED_FILES}/after_delete.expected after_delete.test
'

test_expect_success 'delete a bank' '
    flux account delete-bank A
'

test_expect_success 'print hierarchy again and check that deleted bank or users do not show up in hierarchy' '
    flux account-shares -p ${DB_PATH} > after_bank_delete.test &&
    test_cmp ${EXPECTED_FILES}/after_bank_delete.expected after_bank_delete.test
'

test_expect_success 'add some sub banks and some users' '
    flux account add-bank --parent-bank=root D 1 &&
    flux account add-bank --parent-bank=root E 1 &&
    flux account add-bank --parent-bank=D F 1 &&
    flux account add-user --username=user1001 --userid=1001 --bank=F &&
    flux account add-user --username=user1002 --userid=1002 --bank=F
'

test_expect_success 'check hierarchy before changing parent bank of F' '
    flux account-shares -p ${DB_PATH} > before_parent_bank_change.test &&
    test_cmp ${EXPECTED_FILES}/before_parent_bank_change.expected before_parent_bank_change.test
'

test_expect_success 'change parent bank of F' '
    flux account edit-bank F --parent-bank=E
'

test_expect_success 'check hierarchy after changing parent bank of F' '
    flux account-shares -p ${DB_PATH} > after_parent_bank_change.test &&
    test_cmp ${EXPECTED_FILES}/after_parent_bank_change.expected after_parent_bank_change.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
