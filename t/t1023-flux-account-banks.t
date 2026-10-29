#!/bin/bash

test_description='test flux-account commands that deal with banks'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db
EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/flux_account

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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

test_expect_success 'call view-bank with a format string (bank_id, bank, shares)' '
	flux account view-bank -o "{bank_id:<8} || {bank:<12} || {shares:<5}" A > A_format_string.out &&
	grep "bank_id  || bank         || shares" A_format_string.out &&
	grep "2        || A            || 1" A_format_string.out
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

test_expect_success 'edit a bank cutoff with a human-readable timestamp' '
	flux account edit-bank A --ignore-older-than="Jan 1, 1990 8am" &&
	flux account view-bank A > edited_bank_timestamp.out &&
	jq -e ".[0].ignore_older_than == 631180800" edited_bank_timestamp.out
'

test_expect_success 'reject an invalid bank cutoff without editing other fields' '
	test_must_fail flux account edit-bank A --shares=99 \
		--ignore-older-than=not-a-timestamp > invalid_bank_timestamp.out 2>&1 &&
	grep "not a valid timestamp" invalid_bank_timestamp.out &&
	flux account view-bank A > unchanged_bank.out &&
	jq -e ".[0].shares == 1 and .[0].ignore_older_than == 631180800" \
		unchanged_bank.out
'

test_expect_success 'try to edit a field in a bank account with a bad value' '
	test_must_fail flux account edit-bank C --shares=-1000 > bad_edited_value.out 2>&1 &&
	grep "new shares amount must be > 0" bad_edited_value.out
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

test_expect_success 'combining --tree with --fields does not work' '
	test_must_fail flux account view-bank root --tree --fields=bank_id > error.out 2>&1 &&
	grep "tree option does not support custom formatting" error.out
'

test_expect_success 'call list-banks with a format string' '
	flux account list-banks -o "{bank_id:<7}||{bank:<7}||{shares:>2}" > format_string.out &&
	grep "bank_id||bank   ||shares" format_string.out &&
	grep "1      ||root   || 1" format_string.out
'

test_expect_success 'delete a bank with --force; ensure users also get deleted' '
	flux account delete-bank C --force &&
	test_must_fail flux account view-bank C > nonexistent_bank.out 2>&1 &&
	grep "bank C not found in bank_table" nonexistent_bank.out &&
	test_must_fail flux account view-user user5014 > nonexistent_user.out 2>&1 &&
	grep "user user5014 not found in association_table" nonexistent_user.out
'

test_expect_success 'delete a bank with multiple sub-banks and users with --force' '
	flux account delete-bank D --force &&
	test_must_fail flux account view-bank E > bankE_noexist.out 2>&1 &&
	grep "bank E not found in bank_table" bankE_noexist.out &&
	test_must_fail flux account view-bank F > bankF_noexist.out 2>&1 &&
	grep "bank F not found in bank_table" bankF_noexist.out &&
	test_must_fail flux account view-user user5030 > nonexistent_user.out 2>&1 &&
	grep "user user5030 not found in association_table" nonexistent_user.out
'

test_expect_success 'add a bank with a specified priority' '
	flux account add-bank --parent-bank=root H 1 --priority=1000.567 &&
	flux account view-bank H > bank_H.out &&
	grep "\"priority\": 1000.567" bank_H.out
'

test_expect_success 'edit the priority of a bank' '
	flux account edit-bank H --priority=5000 &&
	flux account view-bank H > bank_H_edited.out &&
	grep "\"priority\": 5000.0" bank_H_edited.out
'

test_expect_success 'add a new bank with a set of users' '
	flux account add-bank --parent-bank=root Z 1 &&
	flux account add-user --username=user90001 --bank=Z &&
	flux account add-user --username=user90002 --bank=Z
'

test_expect_success 'view-bank --parsable --tree lists active column in default output' '
	flux account view-bank --parsable --tree Z > view_bank_tree1.test &&
	cat view_bank_tree1.test &&
	cat <<-EOF >view_bank_tree1.expected &&
	Bank|Username|Active|RawShares|RawUsage|Fairshare
	Z||true|1|0.0
	 Z|user90001|true|1|0.0|0.5
	 Z|user90002|true|1|0.0|0.5

	EOF
	test_cmp view_bank_tree1.test view_bank_tree1.expected
'

test_expect_success 'view-bank --tree lists active column in default output' '
	flux account view-bank --tree Z > view_bank_tree2.test &&
	cat <<-EOF >view_bank_tree2.expected &&
	Bank                            Username              Active           RawShares            RawUsage           Fairshare
	Z                                                       true                   1                 0.0
	 Z                             user90001                true                   1                 0.0                 0.5
	 Z                             user90002                true                   1                 0.0                 0.5

	EOF
	test_cmp view_bank_tree2.test view_bank_tree2.expected
'

test_expect_success 'view-bank --users lists active column in default output' '
	flux account view-bank --users Z > view_bank_users1.test &&
	cat <<-EOF > view_bank_users1.expected &&
	username  | active | default_bank | shares | job_usage | fairshare
	----------+--------+--------------+--------+-----------+----------
	user90001 | 1      | Z            | 1      | 0.0       | 0.5      
	user90002 | 1      | Z            | 1      | 0.0       | 0.5 
	EOF
	grep -f view_bank_users1.test view_bank_users1.expected
'

test_expect_success 'disable one of the users in bank Z' '
	flux account delete-user user90002 Z
'

test_expect_success 'view-bank --parsable --tree lists active column in default output' '
	flux account view-bank --parsable --tree Z > view_bank_tree3.test &&
	cat <<-EOF >view_bank_tree3.expected &&
	Bank|Username|Active|RawShares|RawUsage|Fairshare
	Z||true|1|0.0
	 Z|user90001|true|1|0.0|0.5
	 Z|user90002|false|1|0.0|0.5

	EOF
	test_cmp view_bank_tree3.test view_bank_tree3.expected
'

test_expect_success 'view-bank --tree lists active column in default output' '
	flux account view-bank --tree Z > view_bank_tree4.test &&
	cat <<-EOF >view_bank_tree4.expected &&
	Bank                            Username              Active           RawShares            RawUsage           Fairshare
	Z                                                       true                   1                 0.0
	 Z                             user90001                true                   1                 0.0                 0.5
	 Z                             user90002               false                   1                 0.0                 0.5

	EOF
	test_cmp view_bank_tree4.test view_bank_tree4.expected
'

test_expect_success 'view-bank --users lists active column in default output' '
	flux account view-bank --users Z > view_bank_users2.test &&
	cat <<-EOF > view_bank_users2.expected &&
	username  | active | default_bank | shares | job_usage | fairshare
	----------+--------+--------------+--------+-----------+----------
	user90001 | 1      | Z            | 1      | 0.0       | 0.5      
	user90002 | 0      | Z            | 1      | 0.0       | 0.5 
	EOF
	grep -f view_bank_users2.test view_bank_users2.expected
'

test_expect_success 'view-bank --active --tree only shows active users under that bank' '
	flux account view-bank --active --tree Z > view_bank_tree5.test &&
	cat <<-EOF >view_bank_tree5.expected &&
	Bank                            Username              Active           RawShares            RawUsage           Fairshare
	Z                                                       true                   1                 0.0
	 Z                             user90001                true                   1                 0.0                 0.5

	EOF
	test_cmp view_bank_tree5.test view_bank_tree5.expected
'

test_expect_success 'view-bank --active --parsable --tree only shows active users under that bank' '
	flux account view-bank --parsable --tree --active Z > view_bank_tree6.test &&
	cat <<-EOF >view_bank_tree6.expected &&
	Bank|Username|Active|RawShares|RawUsage|Fairshare
	Z||true|1|0.0
	 Z|user90001|true|1|0.0|0.5

	EOF
	test_cmp view_bank_tree6.test view_bank_tree6.expected
'

test_expect_success 'view-bank --users --active only shows active users under that bank' '
	flux account view-bank --users --active Z > view_bank_users3.test &&
	cat <<-EOF > view_bank_users3.expected &&
	username  | active | default_bank | shares | job_usage | fairshare
	----------+--------+--------------+--------+-----------+----------
	user90001 | 1      | Z            | 1      | 0.0       | 0.5      
	EOF
	grep -f view_bank_users3.test view_bank_users3.expected
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
