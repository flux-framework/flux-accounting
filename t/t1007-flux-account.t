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
	grep -c "user5011" user_info.out > num_rows.test &&
	cat <<-EOF >num_rows.expected &&
	1
	EOF
	test_cmp num_rows.expected num_rows.test
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
	flux account -p ${DB_PATH} view-user user5011 > good_user.test &&
	grep "creation_time" good_user.test
'

test_expect_success 'edit a field in a user account' '
	flux account -p ${DB_PATH} edit-user user5011 --shares 50
'

test_expect_success 'edit a field in a bank account' '
	flux account -p ${DB_PATH} edit-bank C --shares=50 &&
	flux account -p ${DB_PATH} view-bank C > edited_bank.test &&
	grep "50" edited_bank.test
'

test_expect_success 'remove a bank (and any corresponding users that belong to that bank)' '
	flux account -p ${DB_PATH} delete-bank C
'

test_expect_success 'make sure both the DB and the user are successfully removed from DB' '
	flux account -p ${DB_PATH} view-bank C > deleted_bank.out &&
	grep "Bank not found in bank_table" deleted_bank.out &&
	flux account -p ${DB_PATH} view-user user5014 > deleted_user.out &&
	grep "User not found in association_table" deleted_user.out
'

test_expect_success 'remove a user account' '
	flux account -p ${DB_PATH} delete-user user5012 A
'

test_expect_success 'make sure the user is successfully removed from the DB' '
	flux account -p ${DB_PATH} view-user user5012 > deleted_user.out &&
	grep "User not found in association_table" deleted_user.out
'

test_expect_success 'add a queue with no optional args to the queue_table' '
	flux account -p ${DB_PATH} add-queue queue_1
	flux account -p ${DB_PATH} view-queue queue_1 > new_queue.test &&
	cat <<-EOF >new_queue.expected
	queue              min_nodes_per_job  max_nodes_per_job  max_time_per_job   priority           
	queue_1            1                  1                  60                 0                  
	EOF
	test_cmp new_queue.expected new_queue.test
	'

test_expect_success 'add another queue with some optional args' '
	flux account -p ${DB_PATH} add-queue queue_2 --min-nodes-per-job=1 --max-nodes-per-job=10 --max-time-per-job=120
'

test_expect_success 'edit some queue information' '
	flux account -p ${DB_PATH} edit-queue queue_1 --max-nodes-per-job 100
'

test_expect_success 'edit multiple columns for one queue' '
	flux account -p ${DB_PATH} edit-queue queue_1 --min-nodes-per-job 1 --max-nodes-per-job 128 --max-time-per-job 120
'

test_expect_success 'reset a queue limit' '
	flux account -p ${DB_PATH} edit-queue queue_1 --max-nodes-per-job -1 &&
	flux account -p ${DB_PATH} view-queue queue_1 > reset_limit.test &&
	cat <<-EOF >reset_limit.expected
	queue              min_nodes_per_job  max_nodes_per_job  max_time_per_job   priority           
	queue_1            1                  1                  120                0                  
	EOF
	test_cmp reset_limit.expected reset_limit.test
'

test_expect_success 'remove a queue from the queue_table' '
	flux account -p ${DB_PATH} delete-queue queue_2
'

test_expect_success 'make sure the queue is successfully removed from the DB' '
	flux account -p ${DB_PATH} view-queue queue_2 > deleted_queue.out &&
	grep "Queue not found in queue_table" deleted_queue.out
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_done
