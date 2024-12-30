#!/bin/bash

test_description='test flux-account commands that deal with users'

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

test_expect_success 'add some projects to the project_table' '
	flux account add-project project_1 &&
	flux account add-project project_2 &&
	flux account add-project project_3 &&
	flux account add-project project_4
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue standby --priority=0 &&
	flux account add-queue expedite --priority=10000 &&
	flux account add-queue special --priority=99999
'

test_expect_success 'call add-user without specifying a username' '
	test_must_fail flux account add-user --bank=A > error.out 2>&1 &&
	grep "add-user: error: the following arguments are required: --username" error.out
'

test_expect_success 'call add-user without specifying a bank' '
	test_must_fail flux account add-user --username=user5011 > error.out 2>&1 &&
	grep "add-user: error: the following arguments are required: --bank" error.out
'

test_expect_success 'trying to add an association that already exists should raise an IntegrityError' '
	test_must_fail flux account add-user --username=user5011 --userid=5011 --bank=A > already_exists.out 2>&1 &&
	grep "association user5011,A already active in association_table" already_exists.out
'

test_expect_success 'view some user information' '
	flux account view-user user5011 > user_info.out &&
	grep "\"username\": \"user5011\"" user_info.out &&
	grep "\"userid\": 5011" user_info.out &&
	grep "\"bank\": \"A\"" user_info.out
'

test_expect_success 'view some user information with --parsable' '
	flux account view-user --parsable user5011 > user_info_parsable.out &&
	grep -w "user5011\|5011\|A" user_info_parsable.out
'

test_expect_success 'edit a userid for a user' '
	flux account edit-user user5011 --userid=12345 &&
	flux account view-user user5011 > edit_userid.out &&
	grep -w "user5011\|12345\|A" edit_userid.out &&
	flux account edit-user user5011 --userid=5011
'

test_expect_success 'edit the max_active_jobs of an existing user' '
	flux account edit-user user5011 --max-active-jobs 999 &&
	flux account view-user user5011 > edited_shares.out &&
	grep -w "user5011\|5011\|999" edited_shares.out
'

test_expect_success 'trying to view a user who does not exist in the DB should raise a ValueError' '
	test_must_fail flux account view-user user9999 > user_nonexistent.out 2>&1 &&
	grep "view-user: user user9999 not found in association_table" user_nonexistent.out
'

test_expect_success 'trying to view a user that does exist in the DB should return some information' '
	flux account view-user user5011 > good_user.out &&
	grep -w "user5011\|5011\|A" good_user.out
'

test_expect_success 'edit a field in a user account' '
	flux account edit-user user5011 --shares 50
'

test_expect_success 'remove a user account' '
	flux account delete-user user5012 A &&
	flux account view-user user5012 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
