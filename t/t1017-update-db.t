#!/bin/bash

test_description='Test flux account-update-db command'
. `dirname $0`/sharness.sh

DB_PATHv1=$(pwd)/FluxAccountingTestv1.db
DB_PATHv2=$(pwd)/FluxAccountingTestv2.db
DB_v0_10_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-10-0.db
DB_v0_11_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-11-0.db
DB_v0_12_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-12-0.db
DB_v0_13_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-13-0.db
DB_v0_14_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-14-0.db
DB_v0_15_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-15-0.db
DB_v0_16_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-16-0.db
DB_v0_17_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-17-0.db
DB_v0_18_0=${SHARNESS_TEST_SRCDIR}/expected/test_dbs/FluxAccountingv0-18-0.db
MODIFY_DB=${SHARNESS_TEST_SRCDIR}/scripts/modify_accounting_db.py
CHECK_TABLES=${SHARNESS_TEST_SRCDIR}/scripts/check_db_info.py

test_expect_success 'create a flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTestv1.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATHv1} add-bank root 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root A 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root B 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root C 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=root D 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=D E 1 &&
	flux account -p ${DB_PATHv1} add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account -p ${DB_PATHv1} add-user --username=user5011 --userid=5011 --bank=A &&
	flux account -p ${DB_PATHv1} add-user --username=user5012 --userid=5012 --bank=A &&
	flux account -p ${DB_PATHv1} add-user --username=user5013 --userid=5013 --bank=B &&
	flux account -p ${DB_PATHv1} add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'create a new flux-accounting DB with an additional table, additional columns in existing tables, and a removed column' '
	flux python ${MODIFY_DB} ${DB_PATHv2}
'

test_expect_success 'run flux account-update-db' '
	flux account-update-db -p ${DB_PATHv1} --new-db ${DB_PATHv2}
'

test_expect_success 'get all the tables of the old DB and check that new table was added' '
	flux python ${CHECK_TABLES} -p ${DB_PATHv1} -t > tables.test &&
	cat <<-EOF >tables.expected
	sqlite_sequence
	association_table
	bank_table
	job_usage_factor_table
	t_half_life_period_table
	organization
	queue_table
	EOF
	test_cmp tables.expected tables.test
'

test_expect_success 'get all the columns of the updated table in the DB and check that new columns were added' '
	flux python ${CHECK_TABLES} -p ${DB_PATHv1} -c association_table > association_table_columns.test &&
	cat <<-EOF >association_table_columns.expected
	table name: association_table
	creation_time
	mod_time
	active
	username
	userid
	bank
	default_bank
	shares
	job_usage
	fairshare
	max_running_jobs
	max_active_jobs
	max_nodes
	queues
	organization
	yrs_experience
	EOF
	test_cmp association_table_columns.expected association_table_columns.test
'

test_expect_success 'get all the columns from the queue_table and make sure the dropped column does not show up' '
	flux python ${CHECK_TABLES} -p ${DB_PATHv1} -c queue_table > queue_table_columns.test &&
	cat <<-EOF >queue_table_columns.expected
	table name: queue_table
	queue
	min_nodes_per_job
	max_nodes_per_job
	priority
	EOF
	test_cmp queue_table_columns.expected queue_table_columns.test
'

test_expect_success 'successfully update flux-accounting DB from v0.10.0' '
	cp ${DB_v0_10_0} tmp_v0_10_0.db &&
	chmod 666 tmp_v0_10_0.db &&
	flux account-update-db -p tmp_v0_10_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.11.0' '
	cp ${DB_v0_11_0} tmp_v0_11_0.db &&
	chmod 666 tmp_v0_11_0.db &&
	flux account-update-db -p tmp_v0_11_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.12.0' '
	cp ${DB_v0_12_0} tmp_v0_12_0.db &&
	chmod 666 tmp_v0_12_0.db &&
	flux account-update-db -p tmp_v0_12_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.13.0' '
	cp ${DB_v0_13_0} tmp_v0_13_0.db &&
	chmod 666 tmp_v0_13_0.db &&
	flux account-update-db -p tmp_v0_13_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.14.0' '
	cp ${DB_v0_14_0} tmp_v0_14_0.db &&
	chmod 666 tmp_v0_14_0.db &&
	flux account-update-db -p tmp_v0_14_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.15.0' '
	cp ${DB_v0_15_0} tmp_v0_15_0.db &&
	chmod 666 tmp_v0_15_0.db &&
	flux account-update-db -p tmp_v0_15_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.16.0' '
	cp ${DB_v0_16_0} tmp_v0_16_0.db &&
	chmod 666 tmp_v0_16_0.db &&
	flux account-update-db -p tmp_v0_16_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.17.0' '
	cp ${DB_v0_17_0} tmp_v0_17_0.db &&
	chmod 666 tmp_v0_17_0.db &&
	flux account-update-db -p tmp_v0_17_0.db
'

test_expect_success 'successfully update flux-accounting DB from v0.18.0' '
	cp ${DB_v0_18_0} tmp_v0_18_0.db &&
	chmod 666 tmp_v0_18_0.db &&
	flux account-update-db -p tmp_v0_18_0.db
'

test_expect_success 'remove temporary test DBs' '
	rm tmp_v0_10_0.db &&
	rm tmp_v0_11_0.db &&
	rm tmp_v0_12_0.db &&
	rm tmp_v0_13_0.db &&
	rm tmp_v0_14_0.db &&
	rm tmp_v0_15_0.db &&
	rm tmp_v0_16_0.db &&
	rm tmp_v0_17_0.db &&
	rm tmp_v0_18_0.db
'

test_done
