#!/bin/bash

test_description='Test flux-account commands'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root A 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root B 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root C 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root D 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=D E 1
	flux account -p ${DB_PATH} add-bank --parent-bank=D F 1
'

test_expect_success 'add some users to the DB' '
	flux account -p ${DB_PATH} add-user --username=user5011 --userid=5011 --bank=A &&
	flux account -p ${DB_PATH} add-user --username=user5012 --userid=5012 --bank=A &&
	flux account -p ${DB_PATH} add-user --username=user5013 --userid=5013 --bank=B &&
	flux account -p ${DB_PATH} add-user --username=user5014 --userid=5014 --bank=C
'

test_expect_success 'add some queues to the DB' '
	flux account -p ${DB_PATH} add-queue standby --priority=0 &&
	flux account -p ${DB_PATH} add-queue expedite --priority=10000 &&
	flux account -p ${DB_PATH} add-queue special --priority=99999
'

test_expect_success 'view some user information' '
	flux account -p ${DB_PATH} view-user user5011 > user_info.out &&
	grep "user5011" | grep "5011" | grep "A" user_info.out
'

test_expect_success 'add a queue to an existing user account' '
	flux account -p ${DB_PATH} edit-user user5011 --queue="expedite"
'

test_expect_success 'trying to add a non-existent queue to a user account should return an error' '
	flux account -p ${DB_PATH} edit-user user5011 --queue="foo" > bad_queue.out &&
	grep "Queue specified does not exist in queue_table" bad_queue.out
'

test_expect_success 'trying to add a user with a non-existent queue should also return an error' '
	flux account -p ${DB_PATH} add-user --username=user5015 --userid=5015 --bank=A --queue="foo" > bad_queue2.out &&
	grep "Queue specified does not exist in queue_table" bad_queue2.out
'

test_expect_success 'add multiple queues to an existing user account' '
	flux account -p ${DB_PATH} edit-user user5012 --queue="expedite,standby" &&
	flux account -p ${DB_PATH} view-user user5012 > user5012.out &&
	grep "expedite,standby" user5012.out
'

test_expect_success 'edit the max_active_jobs of an existing user' '
	flux account -p ${DB_PATH} edit-user user5011 --max-active-jobs 999 &&
	flux account -p ${DB_PATH} view-user user5011 > edited_shares.out &&
	grep "user5011" | grep "5011" | grep "999" edited_shares.out
'

test_expect_success 'edit a queue priority' '
	flux account -p ${DB_PATH} edit-queue expedite --priority=20000 &&
	flux account -p ${DB_PATH} view-queue expedite > edited_queue.out &&
	grep "20000" edited_queue.out
'

test_expect_success 'remove a queue' '
	flux account -p ${DB_PATH} delete-queue special &&
	flux account -p ${DB_PATH} view-queue special > deleted_queue.out &&
	grep "Queue not found in queue_table" deleted_queue.out
'

test_expect_success 'trying to view a bank that does not exist in the DB should return an error message' '
	flux account -p ${DB_PATH} view-bank foo > bad_bank.out &&
	grep "Bank not found in bank_table" bad_bank.out
'

test_expect_success 'viewing the root bank with no optional args should show just the bank info' '
	flux account -p ${DB_PATH} view-bank root > root_bank.test &&
	test_cmp ${EXPECTED_FILES}/root_bank.expected root_bank.test
'

test_expect_success 'viewing the root bank with -t should show the entire hierarchy' '
	flux account -p ${DB_PATH} view-bank root -t > full_hierarchy.test &&
	test_cmp ${EXPECTED_FILES}/full_hierarchy.expected full_hierarchy.test
'

test_expect_success 'viewing a bank with users in it should print all user info under that bank as well' '
	flux account -p ${DB_PATH} view-bank A -u > A_bank.test &&
	test_cmp ${EXPECTED_FILES}/A_bank.expected A_bank.test
'

test_expect_success 'viewing a bank with sub banks should return a smaller hierarchy tree' '
	flux account -p ${DB_PATH} view-bank D -t > D_bank.test &&
	test_cmp ${EXPECTED_FILES}/D_bank.expected D_bank.test
'

test_expect_success 'trying to view a user who does not exist in the DB should return an error message' '
	flux account -p ${DB_PATH} view-user user9999 > bad_user.out &&
	grep "User not found in association_table" bad_user.out
'

test_expect_success 'trying to view a user that does exist in the DB should return some information' '
	flux account -p ${DB_PATH} view-user user5011 > good_user.out &&
	grep "user5011" | grep "5011" | grep "A" good_user.out
'

test_expect_success 'edit a field in a user account' '
	flux account -p ${DB_PATH} edit-user user5011 --shares 50
'

test_expect_success 'edit a field in a bank account' '
	flux account -p ${DB_PATH} edit-bank C --shares=50 &&
	flux account -p ${DB_PATH} view-bank C > edited_bank.out &&
	grep "C" | grep "50" edited_bank.out
'

test_expect_success 'remove a bank (and any corresponding users that belong to that bank)' '
	flux account -p ${DB_PATH} delete-bank C &&
	flux account -p ${DB_PATH} view-bank C > deleted_bank.test &&
	grep -f ${EXPECTED_FILES}/deleted_bank.expected deleted_bank.test &&
	flux account -p ${DB_PATH} view-user user5014 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'remove a user account' '
	flux account -p ${DB_PATH} delete-user user5012 A &&
	flux account -p ${DB_PATH} view-user user5012 > deleted_user.out &&
	grep -f ${EXPECTED_FILES}/deleted_user.expected deleted_user.out
'

test_expect_success 'add a queue with no optional args to the queue_table' '
	flux account -p ${DB_PATH} add-queue queue_1
	flux account -p ${DB_PATH} view-queue queue_1 > new_queue.out &&
	grep "queue_1" | grep "1" | grep "1" | grep "60" | grep "0" new_queue.out
	'

test_expect_success 'add another queue with some optional args' '
	flux account -p ${DB_PATH} add-queue queue_2 --min-nodes-per-job=1 --max-nodes-per-job=10 --max-time-per-job=120
'

test_expect_success 'edit some queue information' '
	flux account -p ${DB_PATH} edit-queue queue_1 --max-nodes-per-job 100 &&
	flux account -p ${DB_PATH} view-queue queue_1 > edited_max_nodes.out &&
	grep "queue_1" | grep "100" edited_max_nodes.out
'

test_expect_success 'edit multiple columns for one queue' '
	flux account -p ${DB_PATH} edit-queue queue_1 --min-nodes-per-job 1 --max-nodes-per-job 128 --max-time-per-job 120
'

test_expect_success 'reset a queue limit' '
	flux account -p ${DB_PATH} edit-queue queue_1 --max-nodes-per-job -1 &&
	flux account -p ${DB_PATH} view-queue queue_1 > reset_limit.out &&
	grep "queue_1" | grep "1" | grep "1" | grep "120" | grep "0" reset_limit.out
'

test_expect_success 'remove a queue from the queue_table' '
	flux account -p ${DB_PATH} delete-queue queue_2 &&
	flux account -p ${DB_PATH} view-queue queue_2 > deleted_queue.out &&
	grep "Queue not found in queue_table" deleted_queue.out
'

test_expect_success 'Add a user to two different banks' '
	flux account -p ${DB_PATH} add-user --username=user5015 --userid=5015 --bank=E &&
	flux account -p ${DB_PATH} add-user --username=user5015 --userid=5015 --bank=F
'

test_expect_success 'Delete user default bank row' '
	flux account -p ${DB_PATH} delete-user user5013 E
'

test_expect_success 'Check that user default bank gets updated to other bank' '
	flux account -p ${DB_PATH} view-user user5015 > new_default_bank.out &&
	cat new_default_bank.out &&
	grep "user5015" | grep "F" | grep "F" new_default_bank.out
'

test_expect_success 'add some projects to the project_table' '
	flux account -p ${DB_PATH} add-project project_1 &&
	flux account -p ${DB_PATH} add-project project_2 &&
	flux account -p ${DB_PATH} add-project project_3 &&
	flux account -p ${DB_PATH} add-project project_4
'

test_expect_success 'view project information from the project_table' '
	flux account -p ${DB_PATH} view-project project_1 > project_1.out &&
	grep "1" | grep "project_1" project_1.out
'

test_expect_success 'add a user with some specified projects to the association_table' '
	flux account -p ${DB_PATH} add-user --username=user5015 --bank=A --projects="project_1,project_3" &&
	flux account -p ${DB_PATH} view-user user5015 > user5015_info.out &&
	grep "user5015" | grep "project_1,project_3,*" user5015_info.out
'

test_expect_success 'adding a user with a non-existing project should fail' '
	flux account -p ${DB_PATH} add-user --username=user5016 --bank=A --projects="project_1,foo" > bad_project.out &&
	grep "Project \"foo\" does not exist in project_table" bad_project.out
'

test_expect_success 'successfully edit a projects list for a user' '
	flux account -p ${DB_PATH} edit-user user5015 --bank=A --projects="project_1,project_2,project_3" &&
	flux account -p ${DB_PATH} view-user user5015 > user5015_edited_info.out &&
	grep "user5015" | grep "project_1,project_2,project_3,*" user5015_edited_info.out
'

test_expect_success 'editing a user project list with a non-existing project should fail' '
	flux account -p ${DB_PATH} edit-user user5015 --bank=A --projects="project_1,foo" > bad_project_2.out &&
	grep "Project \"foo\" does not exist in project_table" bad_project_2.out
'

test_expect_success 'remove a project from the project_table that is still referenced by at least one user' '
	flux account -p ${DB_PATH} delete-project project_1 > warning_message.out &&
	flux account -p ${DB_PATH} view-project project_1 > deleted_project.out &&
	grep "WARNING: user(s) in the assocation_table still reference this project." warning_message.out &&
	grep "Project not found in project_table" deleted_project.out
'

test_expect_success 'remove a project that is not referenced by any users' '
	flux account -p ${DB_PATH} delete-project project_4 &&
	flux account -p ${DB_PATH} view-project project_4 > deleted_project_2.out &&
	grep "Project not found in project_table" deleted_project_2.out
'

test_expect_success 'add a user to the accounting DB without specifying any projects' '
	flux account -p ${DB_PATH} add-user --username=user5017 --bank=A &&
	flux account -p ${DB_PATH} view-user user5017 > default_project_unspecified.test &&
	cat <<-EOF >default_project_unspecfied.expected
	default_project
	*
	EOF
	grep -f default_project_unspecfied.expected default_project_unspecified.test
'

test_expect_success 'add a user to the accounting DB and specify a project' '
	flux account -p ${DB_PATH} add-user --username=user5018 --bank=A --projects=project_2 &&
	flux account -p ${DB_PATH} view-user user5018 > default_project_specified.test &&
	cat <<-EOF >default_project_specified.expected
	default_project
	project_2
	EOF
	grep -f default_project_specified.expected default_project_specified.test
'

test_expect_success 'edit the default project of a user' '
	flux account -p ${DB_PATH} edit-user user5018 --default-project=* &&
	flux account -p ${DB_PATH} view-user user5018 > edited_default_project.test &&
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

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_done
