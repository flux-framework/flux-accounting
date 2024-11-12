#!/bin/bash

test_description='test exporting flux-accounting database data into .csv files'
. `dirname $0`/sharness.sh

DB_PATHv1=$(pwd)/FluxAccountingTestv1.db
DB_PATHv2=$(pwd)/FluxAccountingTestv2.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/pop_db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTestv1.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATHv1} -t
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=root D 1 &&
	flux account add-bank --parent-bank=D E 1
	flux account add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user5011 --userid=5011 --bank=A &&
	flux account add-user --username=user5012 --userid=5012 --bank=A &&
	flux account add-user --username=user5013 --userid=5013 --bank=B &&
	flux account add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'export DB information into .csv files' '
	flux account export-db
'

test_expect_success 'compare banks.csv' '
	cat <<-EOF >bank_table_expected.csv
	bank_id,bank,active,parent_bank,shares,job_usage,priority
	1,root,1,,1,0.0,0.0
	2,A,1,root,1,0.0,0.0
	3,B,1,root,1,0.0,0.0
	4,C,1,root,1,0.0,0.0
	5,D,1,root,1,0.0,0.0
	6,E,1,D,1,0.0,0.0
	7,F,1,D,1,0.0,0.0
	EOF
	test_cmp -b bank_table_expected.csv bank_table.csv
'

# use 'grep' checks here because the contents of association_table also
# store timestamps of when the user was added to the DB, and thus will be
# slightly different every time these tests are run
test_expect_success 'make association_table.csv is populated' '
	grep "creation_time,mod_time,active,username" association_table.csv &&
	grep "user5011,5011,A,A" association_table.csv &&
	grep "user5012,5012,A,A" association_table.csv &&
	grep "user5013,5013,B,B" association_table.csv &&
	grep "user5014,5014,C,C" association_table.csv
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
