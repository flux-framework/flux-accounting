#!/bin/bash

test_description='Test populating a flux-accounting DB with pop-db command and .csv files'
. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/pop_db

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

test_expect_success 'try to populate flux-accounting DB with a bad filename' '
	touch foo.csv &&
	test_must_fail flux account pop-db -c foo.csv > error.out 2>&1 &&
	grep "table \"foo\" does not exist in the database" error.out
'

test_expect_success 'create bank_table.csv' '
	cat <<-EOF >bank_table.csv
	bank,parent_bank,shares
	root,,1
	A,root,1
	B,root,1
	C,root,1
	D,C,1
	EOF
'

test_expect_success 'populate flux-accounting DB with bank_table.csv' '
	flux account pop-db -c bank_table.csv
'

test_expect_success 'create association_table.csv' '
	cat <<-EOF >association_table.csv
	creation_time,username,userid,bank,default_bank,shares,max_running_jobs,max_active_jobs,max_nodes,queues
	0,user1000,1000,A,A,1,10,15,5,""
	0,user1001,1001,A,A,1,10,15,5,""
	0,user1002,1002,A,A,1,10,15,5,""
	0,user1003,1003,A,A,1,10,15,5,""
	0,user1004,1004,A,A,1,10,15,5,""
	EOF
'

test_expect_success 'populate association_table with association_table.csv' '
	flux account pop-db -c association_table.csv
'

test_expect_success 'check database hierarchy to make sure all banks & users were added' '
	flux account view-bank root -t > db_hierarchy_base.test &&
	test_cmp ${EXPECTED_FILES}/db_hierarchy_base.expected db_hierarchy_base.test
'

test_expect_success 'create association_table.csv with some missing user information' '
	cat <<-EOF >association_table.csv
	creation_time,username,userid,bank,default_bank,shares,max_running_jobs,max_active_jobs,max_nodes,queues
	0,user1005,1005,B,B,1,5,,5,""
	0,user1006,1006,B,B,,,,5,""
	0,user1007,1007,B,B,1,7,,,""
	0,user1008,1008,B,B,,,,5,""
	0,user1009,1009,B,B,1,9,,,""
	EOF
'

test_expect_success 'populate association_table' '
	flux account pop-db -c association_table.csv
'

test_expect_success 'check database hierarchy to make sure new users were added' '
	flux account view-bank root -t > db_hierarchy_new_users.test &&
	test_cmp ${EXPECTED_FILES}/db_hierarchy_new_users.expected db_hierarchy_new_users.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
