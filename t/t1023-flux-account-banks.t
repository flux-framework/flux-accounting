#!/bin/bash

test_description='test flux-account commands that deal with banks'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

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

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=root D 1 &&
	flux account add-bank --parent-bank=D E 1
	flux account add-bank --parent-bank=D F 1
'

test_expect_success 'add some users' '
	flux account add-user --username=user5011 --userid=5011 --bank=A &&
	flux account add-user --username=user5012 --userid=5012 --bank=A &&
	flux account add-user --username=user5013 --userid=5013 --bank=B &&
	flux account add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'add some queues' '
	flux account add-queue standby --priority=0 &&
	flux account add-queue expedite --priority=10000 &&
	flux account add-queue special --priority=99999
'

test_expect_success 'trying to view a bank that does not exist in the DB should raise a ValueError' '
	test_must_fail flux account view-bank foo > bank_nonexistent.out 2>&1 &&
	grep "bank foo not found in bank_table" bank_nonexistent.out
'

test_expect_success 'viewing the root bank with no optional args should show basic bank info' '
	flux account view-bank root > root_bank.test &&
	test_cmp ${EXPECTED_FILES}/root_bank.expected root_bank.test
'

test_expect_success 'viewing the root bank with -t should show the entire hierarchy' '
	flux account -p ${DB_PATH} view-bank root -t > full_hierarchy.test &&
	test_cmp ${EXPECTED_FILES}/full_hierarchy.expected full_hierarchy.test
'

test_expect_success 'viewing a bank with users in it should print all user info as well' '
	flux account view-bank A -u > A_bank.test &&
	test_cmp ${EXPECTED_FILES}/A_bank.expected A_bank.test
'

test_expect_success 'viewing a leaf bank in hierarchy mode with no users in it works' '
	flux account view-bank F -t > F_bank_tree.test &&
	test_cmp ${EXPECTED_FILES}/F_bank_tree.expected F_bank_tree.test
'

test_expect_success 'viewing a leaf bank in users mode with no users in it works' '
	flux account view-bank F -u > F_bank_users.test &&
	test_cmp ${EXPECTED_FILES}/F_bank_users.expected F_bank_users.test
'

test_expect_success 'viewing a bank with sub banks should return a smaller hierarchy tree' '
	flux account -p ${DB_PATH} view-bank D -t > D_bank.test &&
	test_cmp ${EXPECTED_FILES}/D_bank.expected D_bank.test
'

test_expect_success 'view a bank with sub banks with users in it' '
	flux account add-user --username=user5030 --userid=5030 --bank=E &&
	flux account add-user --username=user5031 --userid=5031 --bank=E &&
	flux account -p ${DB_PATH} view-bank E -t > E_bank.test &&
	test_cmp ${EXPECTED_FILES}/E_bank.expected E_bank.test
'

test_expect_success 'edit a field in a bank account' '
	flux account edit-bank C --shares=50 &&
	flux account view-bank C > edited_bank.out &&
	grep -w "C\|50" edited_bank.out
'

test_expect_success 'try to edit a field in a bank account with a bad value' '
	test_must_fail flux account edit-bank C --shares=-1000 > bad_edited_value.out 2>&1 &&
	grep "new shares amount must be >= 0" bad_edited_value.out
'

test_expect_success 'remove a bank (and any corresponding users that belong to that bank)' '
	flux account delete-bank C &&
	flux account view-bank C > deleted_bank.test &&
	grep -f ${EXPECTED_FILES}/deleted_bank.expected deleted_bank.test &&
	flux account view-user user5014 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'add a user to two different banks' '
	flux account add-user --username=user5015 --userid=5015 --bank=E &&
	flux account add-user --username=user5015 --userid=5015 --bank=F
'

test_expect_success 'delete user default bank row' '
	flux account delete-user user5015 E
'

test_expect_success 'check that user default bank gets updated to other bank' '
	flux account view-user user5015 > new_default_bank.out &&
	grep "\"username\": \"user5015\"" new_default_bank.out
	grep "\"bank\": \"F\"" new_default_bank.out &&
	grep "\"default_bank\": \"F\"" new_default_bank.out
'

test_expect_success 'trying to add a user to a nonexistent bank should raise a ValueError' '
	test_must_fail flux account add-user --username=user5019 --bank=foo > nonexistent_bank.out 2>&1 &&
	grep "Bank foo does not exist in bank_table" nonexistent_bank.out
'

test_expect_success 'call list-banks --help' '
	flux account list-banks --help
'

test_expect_success 'call list-banks' '
	flux account list-banks
'

test_expect_success 'call list-banks and include inactive banks' '
	flux account list-banks --inactive
'

test_expect_success 'call list-banks and customize output' '
	flux account list-banks --fields=bank_id,bank
'

test_expect_success 'call list-banks with a bad field' '
	test_must_fail flux account list-banks --fields=bank_id,foo > error.out 2>&1 &&
	grep "invalid fields: foo" error.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
