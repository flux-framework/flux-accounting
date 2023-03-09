#!/bin/bash

test_description='Test flux-account commands'

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

test_expect_success 'add some queues to the DB' '
	flux account add-queue standby --priority=0 &&
	flux account add-queue expedite --priority=10000 &&
	flux account add-queue special --priority=99999
'

test_expect_success 'view some user information' '
	flux account view-user user5011 > user_info.out &&
	grep "user5011" | grep "5011" | grep "A" user_info.out
'

test_expect_success 'edit a userid for a user' '
	flux account edit-user user5011 --userid=12345 &&
	flux account view-user user5011 > edit_userid.out &&
	grep "user5011" | grep "12345" | grep "A" edit_userid.out &&
	flux account edit-user user5011 --userid=5011
'

test_expect_success 'add a queue to an existing user account' '
	flux account edit-user user5011 --queue="expedite"
'

test_expect_success 'trying to add a non-existent queue to a user account should raise a ValueError' '
	test_must_fail flux account edit-user user5011 --queue="foo" > bad_queue.out 2>&1 &&
	grep "Queue foo does not exist in queue_table" bad_queue.out
'

test_expect_success 'trying to add a user with a non-existent queue should also return an error' '
	test_must_fail flux account add-user --username=user5015 --bank=A --queue="foo" > bad_queue2.out 2>&1 &&
	grep "Queue foo does not exist in queue_table" bad_queue2.out
'

test_expect_success 'add multiple queues to an existing user account' '
	flux account edit-user user5012 --queue="expedite,standby" &&
	flux account view-user user5012 > user5012.out &&
	grep "expedite,standby" user5012.out
'

test_expect_success 'edit the max_active_jobs of an existing user' '
	flux account edit-user user5011 --max-active-jobs 999 &&
	flux account view-user user5011 > edited_shares.out &&
	grep "user5011" | grep "5011" | grep "999" edited_shares.out
'

test_expect_success 'edit a queue priority' '
	flux account edit-queue expedite --priority=20000 &&
	flux account view-queue expedite > edited_queue.out &&
	grep "20000" edited_queue.out
'

test_expect_success 'remove a queue' '
	flux account delete-queue special &&
	test_must_fail flux account view-queue special > deleted_queue.out 2>&1 &&
	grep "Queue special not found in queue_table" deleted_queue.out
'

test_expect_success 'trying to view a bank that does not exist in the DB should raise a ValueError' '
	test_must_fail flux account view-bank foo > bank_nonexistent.out 2>&1 &&
	grep "Bank foo not found in bank_table" bank_nonexistent.out
'

test_expect_success 'viewing the root bank with no optional args should show just the bank info' '
	flux account view-bank root > root_bank.test &&
	test_cmp ${EXPECTED_FILES}/root_bank.expected root_bank.test
'

test_expect_success 'viewing the root bank with -t should show the entire hierarchy' '
	flux account -p ${DB_PATH} view-bank root -t > full_hierarchy.test &&
	test_cmp ${EXPECTED_FILES}/full_hierarchy.expected full_hierarchy.test
'

test_expect_success 'viewing a bank with users in it should print all user info under that bank as well' '
	flux account view-bank A -u > A_bank.test &&
	test_cmp ${EXPECTED_FILES}/A_bank.expected A_bank.test
'

test_expect_success 'viewing a bank with sub banks should return a smaller hierarchy tree' '
	flux account -p ${DB_PATH} view-bank D -t > D_bank.test &&
	test_cmp ${EXPECTED_FILES}/D_bank.expected D_bank.test
'

test_expect_success 'trying to view a user who does not exist in the DB should raise a ValueError' '
	test_must_fail flux account view-user user9999 > user_nonexistent.out 2>&1 &&
	grep "User user9999 not found in association_table" user_nonexistent.out
'

test_expect_success 'trying to view a user that does exist in the DB should return some information' '
	flux account view-user user5011 > good_user.out &&
	grep "user5011" | grep "5011" | grep "A" good_user.out
'

test_expect_success 'edit a field in a user account' '
	flux account edit-user user5011 --shares 50
'

test_expect_success 'edit a field in a bank account' '
	flux account edit-bank C --shares=50 &&
	flux account view-bank C > edited_bank.out &&
	grep "C" | grep "50" edited_bank.out
'

test_expect_success 'try to edit a field in a bank account with a bad value' '
	flux account edit-bank C --shares=-1000 > bad_edited_value.out &&
	grep "New shares amount must be >= 0" bad_edited_value.out
'

test_expect_success 'remove a bank (and any corresponding users that belong to that bank)' '
	flux account delete-bank C &&
	flux account view-bank C > deleted_bank.test &&
	grep -f ${EXPECTED_FILES}/deleted_bank.expected deleted_bank.test &&
	flux account view-user user5014 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'remove a user account' '
	flux account delete-user user5012 A &&
	flux account view-user user5012 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'add a queue with no optional args to the queue_table' '
	flux account add-queue queue_1
	flux account view-queue queue_1 > new_queue.out &&
	grep "queue_1" | grep "1" | grep "1" | grep "60" | grep "0" new_queue.out
'

test_expect_success 'add another queue with some optional args' '
	flux account add-queue queue_2 --min-nodes-per-job=1 --max-nodes-per-job=10 --max-time-per-job=120
'

test_expect_success 'edit some queue information' '
	flux account edit-queue queue_1 --max-nodes-per-job 100 &&
	flux account view-queue queue_1 > edited_max_nodes.out &&
	grep "queue_1" | grep "100" edited_max_nodes.out
'

test_expect_success 'edit multiple columns for one queue' '
	flux account edit-queue queue_1 --min-nodes-per-job 1 --max-nodes-per-job 128 --max-time-per-job 120
'

test_expect_success 'reset a queue limit' '
	flux account edit-queue queue_1 --max-nodes-per-job -1 &&
	flux account view-queue queue_1 > reset_limit.out &&
	grep "queue_1" | grep "1" | grep "1" | grep "120" | grep "0" reset_limit.out
'

test_expect_success 'Trying to view a queue that does not exist should raise a ValueError' '
	test_must_fail flux account view-queue foo > queue_nonexistent.out 2>&1 &&
	grep "Queue foo not found in queue_table" queue_nonexistent.out
'

test_expect_success 'Add a user to two different banks' '
	flux account add-user --username=user5015 --userid=5015 --bank=E &&
	flux account add-user --username=user5015 --userid=5015 --bank=F
'

test_expect_success 'Delete user default bank row' '
	flux account delete-user user5013 E
'

test_expect_success 'Check that user default bank gets updated to other bank' '
	flux account view-user user5015 > new_default_bank.out &&
	cat new_default_bank.out &&
	grep "user5015" | grep "F" | grep "F" new_default_bank.out
'

test_expect_success 'add some projects to the project_table' '
	flux account add-project project_1 &&
	flux account add-project project_2 &&
	flux account add-project project_3 &&
	flux account add-project project_4
'

test_expect_success 'view project information from the project_table' '
	flux account view-project project_1 > project_1.out &&
	grep "1" | grep "project_1" project_1.out
'

test_expect_success 'add a user with some specified projects to the association_table' '
	flux account add-user --username=user5015 --bank=A --projects="project_1,project_3" &&
	flux account view-user user5015 > user5015_info.out &&
	grep "user5015" | grep "project_1,project_3,*" user5015_info.out
'

test_expect_success 'adding a user with a non-existing project should fail' '
	test_must_fail flux account add-user --username=user5016 --bank=A --projects="project_1,foo" > bad_project.out 2>&1 &&
	grep "Project foo does not exist in project_table" bad_project.out
'

test_expect_success 'successfully edit a projects list for a user' '
	flux account edit-user user5015 --bank=A --projects="project_1,project_2,project_3" &&
	flux account view-user user5015 > user5015_edited_info.out &&
	grep "user5015" | grep "project_1,project_2,project_3,*" user5015_edited_info.out
'

test_expect_success 'editing a user project list with a non-existing project should fail' '
	test_must_fail flux account edit-user user5015 --bank=A --projects="project_1,foo" > bad_project_2.out 2>&1 &&
	grep "Project foo does not exist in project_table" bad_project_2.out
'

test_expect_success 'remove a project from the project_table that is still referenced by at least one user' '
	flux account delete-project project_1 > warning_message.out &&
	test_must_fail flux account view-project project_1 > deleted_project.out 2>&1 &&
	grep "WARNING: user(s) in the assocation_table still reference this project." warning_message.out &&
	grep "Project project_1 not found in project_table" deleted_project.out
'

test_expect_success 'remove a project that is not referenced by any users' '
	flux account delete-project project_4 &&
	test_must_fail flux account view-project project_4 > deleted_project_2.out 2>&1 &&
	grep "Project project_4 not found in project_table" deleted_project_2.out
'

test_expect_success 'add a user to the accounting DB without specifying any projects' '
	flux account add-user --username=user5017 --bank=A &&
	flux account view-user user5017 > default_project_unspecified.test &&
	cat <<-EOF >default_project_unspecfied.expected
	default_project
	*
	EOF
	grep -f default_project_unspecfied.expected default_project_unspecified.test
'

test_expect_success 'add a user to the accounting DB and specify a project' '
	flux account add-user --username=user5018 --bank=A --projects=project_2 &&
	flux account view-user user5018 > default_project_specified.test &&
	cat <<-EOF >default_project_specified.expected
	default_project
	project_2
	EOF
	grep -f default_project_specified.expected default_project_specified.test
'

test_expect_success 'edit the default project of a user' '
	flux account edit-user user5018 --default-project=* &&
	flux account view-user user5018 > edited_default_project.test &&
	cat <<-EOF >edited_default_project.expected
	default_project
	*
	EOF
	grep -f edited_default_project.expected edited_default_project.test
	cat <<-EOF >projects_list.expected
	projects
	project_2,*
	EOF
	grep -f projects_list.expected edited_default_project.test
'

test_expect_success 'trying to add a user to a nonexistent bank should raise a ValueError' '
	test_must_fail flux account add-user --username=user5019 --bank=foo > nonexistent_bank.out 2>&1 &&
	grep "Bank foo does not exist in bank_table" nonexistent_bank.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
