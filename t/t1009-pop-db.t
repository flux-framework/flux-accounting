#!/bin/bash

test_description='Test populating a flux-accounting DB with pop-db command and .csv files'
. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/pop_db

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'create a banks.csv file containing bank information' '
	cat <<-EOF >banks.csv
	root,,1
	A,root,1
	B,root,1
	C,root,1
	D,C,1
	EOF
'

test_expect_success 'populate flux-accounting DB with banks.csv' '
	flux account-pop-db -p ${DB_PATH} -b banks.csv
'

test_expect_success 'create a users.csv file containing user information' '
	cat <<-EOF >users.csv
	user1000,1000,A,1,10,15,5,""
	user1001,1001,A,1,10,15,5,""
	user1002,1002,A,1,10,15,5,""
	user1003,1003,A,1,10,15,5,""
	user1004,1004,A,1,10,15,5,""
	EOF
'

test_expect_success 'populate flux-accounting DB with users.csv' '
	flux account-pop-db -p ${DB_PATH} -u users.csv
'

test_expect_success 'check database hierarchy to make sure all banks & users were added' '
	flux account-shares -p ${DB_PATH} > db_hierarchy_base.test &&
	test_cmp ${EXPECTED_FILES}/db_hierarchy_base.expected db_hierarchy_base.test
'

test_expect_success 'create a users.csv file with some missing optional user information' '
	cat <<-EOF >users_optional_vals.csv
	user1005,1005,B,1,5,,5,""
	user1006,1006,B,,,,5,""
	user1007,1007,B,1,7,,,""
	user1008,1008,B,,,,5,""
	user1009,1009,B,1,9,,,""
	EOF
'

test_expect_success 'populate flux-accounting DB with users_optional_vals.csv' '
	flux account-pop-db -p ${DB_PATH} -u users_optional_vals.csv
'

test_expect_success 'check database hierarchy to make sure new users were added' '
	flux account-shares -p ${DB_PATH} > db_hierarchy_new_users.test &&
	test_cmp ${EXPECTED_FILES}/db_hierarchy_new_users.expected db_hierarchy_new_users.test
'

test_done
