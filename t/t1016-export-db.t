#!/bin/bash

test_description='Test flux-account commands'
. `dirname $0`/sharness.sh

DB_PATHv1=$(pwd)/FluxAccountingTestv1.db
DB_PATHv2=$(pwd)/FluxAccountingTestv2.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/pop_db

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTestv1.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATHv1} add-bank root 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root A 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root B 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root C 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root D 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=D E 1
	flux account -p ${DB_PATHv1} add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account -p ${DB_PATHv1} add-user --username=user5011 --userid=5011 --bank=A &&
	flux account -p ${DB_PATHv1} add-user --username=user5012 --userid=5012 --bank=A &&
	flux account -p ${DB_PATHv1} add-user --username=user5013 --userid=5013 --bank=B &&
	flux account -p ${DB_PATHv1} add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'export DB information into .csv files' '
	flux account-export-db -p ${DB_PATHv1}
'

test_expect_success 'compare banks.csv' '
	cat <<-EOF >banks_expected.csv
	root,,1
	A,root,1
	B,root,1
	C,root,1
	D,root,1
	E,D,1
	F,D,1
	EOF
	test_cmp -b banks_expected.csv banks.csv
'

test_expect_success 'compare users.csv' '
	cat <<-EOF >users_expected.csv
	user5011,5011,A,1,5,7,2147483647,
	user5012,5012,A,1,5,7,2147483647,
	user5013,5013,B,1,5,7,2147483647,
	user5014,5014,C,1,5,7,2147483647,
	EOF
	test_cmp -b users_expected.csv users.csv
'

test_expect_success 'create a new flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTestv2.db create-db
'

test_expect_success 'import information into new DB' '
	flux account-pop-db -p ${DB_PATHv2} -b banks.csv &&
	flux account-pop-db -p ${DB_PATHv2} -u users.csv
'

test_expect_success 'compare DB hierarchies to make sure they are the same' '
	flux account-shares -p ${DB_PATHv1} > db1.test &&
	flux account-shares -p ${DB_PATHv2} > db2.test &&
	test_cmp db1.test db2.test
'

test_expect_success 'specify a different filename for exported users and banks .csv files' '
	flux account-export-db -p ${DB_PATHv2} --users foo.csv --banks bar.csv &&
	test_cmp -b users_expected.csv foo.csv &&
	test_cmp -b banks_expected.csv bar.csv
'

test_done
