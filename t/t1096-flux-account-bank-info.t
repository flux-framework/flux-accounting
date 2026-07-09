#!/bin/bash

test_description='test the bank-info command'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'bank-info --help works' '
	flux account bank-info --help
'

# With two child banks under root, each bank will have 50% of the normalized
# shares of root
test_expect_success 'add bank hierarchy' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

# The two associations added to bank A have equal shares in the bank, so their
# normalized shares from inside bank A becomes 50% = 0.5 of the bank
test_expect_success 'add associations to bank A' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=${username} --userid=${uid} --bank=A &&
	flux account add-user --username=user1 --userid=50001 --bank=A
'

# With just one user under bank B, they get 100% of the normalized shares of
# the bank
test_expect_success 'add association to bank B' '
	flux account add-user --username=user2 --userid=50002 --bank=B
'

test_expect_success 'add association to bank C' '
	flux account add-user --username=${username} --userid=${uid} --bank=C
'

test_expect_success 'bank-info full' '
	flux account bank-info -t root
'

test_expect_success 'default shows information for just the association calling it' '
	flux account bank-info > bank_info_default.test &&
	grep "${username}" bank_info_default.test &&
	test_must_fail grep "user1" bank_info_default.test &&
	test_must_fail grep "user2" bank_info_default.test
'

test_expect_success '--verbose shows more detailed output' '
	flux account bank-info -v > bank_info_verbose.test &&
	grep "${username}" bank_info_verbose.test &&
	test_must_fail grep "user1" bank_info_verbose.test &&
	test_must_fail grep "user2" bank_info_verbose.test
'

test_expect_success '--parsable shows parsable output' '
	flux account bank-info -P > bank_info_parsable.test &&
	grep "Name|Shares|Norm_Shares|Norm_Usage|Norm_FS" bank_info_parsable.test &&
	grep "${username}|1|0.166667|0.000000|0.500" bank_info_parsable.test
'

test_expect_success '--no-header suppresses output' '
	flux account bank-info -n > bank_info_no_header.test &&
	test_must_fail \
		grep "Name|Shares|Norm_Shares|Norm_Usage|Norm_FS" bank_info_no_header.test
'

test_expect_success '-x excludes a bank' '
	flux account bank-info -x A > bank_info_no_bank_A.test &&
	test_must_fail grep "A" bank_info_no_bank_A.test &&
	grep "C" bank_info_no_bank_A.test
'

test_expect_success '-t with no bank raises error' '
	test_must_fail flux account bank-info -t > no_bank_passed.err 2>&1 &&
	grep "error: argument -t/--tree: expected one argument" no_bank_passed.err
'

test_expect_success '-t with nonexistent bank raises error' '
	test_must_fail flux account bank-info -t foo > nonexistent_bank_passed.err 2>&1 &&
	grep "bank-info: ValueError: Could not find \"foo\"" nonexistent_bank_passed.err
'

test_expect_success '-t with root bank displays entire tree' '
	flux account bank-info -t root > full_tree.test &&
	grep "root" full_tree.test &&
	grep "A" full_tree.test &&
	grep "B" full_tree.test &&
	grep "C" full_tree.test &&
	grep "${username}" full_tree.test &&
	grep "user1" full_tree.test &&
	grep "user2" full_tree.test
'

test_expect_success '-T with no bank raises error' '
	test_must_fail flux account bank-info -T > no_bank_passed_2.err 2>&1 &&
	grep "error: argument -T/--tree-no-users: expected one argument" no_bank_passed_2.err
'

test_expect_success '-T with root bank displays entire tree with no users' '
	flux account bank-info -T root > full_tree.test &&
	grep "root" full_tree.test &&
	grep "A" full_tree.test &&
	grep "B" full_tree.test &&
	grep "C" full_tree.test &&
	test_must_fail grep "${username}" full_tree.test &&
	test_must_fail grep "user1" full_tree.test &&
	test_must_fail grep "user2" full_tree.test
'

# For this test, we'll add multiple levels of parents to ensure they all show
# up in the output
test_expect_success '-r shows all parents for bank' '
	flux account add-bank --parent-bank=root D 1 &&
	flux account add-bank --parent-bank=D sub_1 1 &&
	flux account add-bank --parent-bank=sub_1 sub_2 1 &&
	flux account add-bank --parent-bank=sub_2 sub_3 1 &&
	flux account bank-info -r sub_3 > bank_info_to_root.test &&
	grep "root" bank_info_to_root.test &&
	grep "D" bank_info_to_root.test &&
	grep "sub_1" bank_info_to_root.test &&
	grep "sub_2" bank_info_to_root.test &&
	grep "sub_3" bank_info_to_root.test
'

test_expect_success '-u with nonexistent user raises error' '
	test_must_fail flux account bank-info -u foo_user > nonexistent_user_passed.err 2>&1 &&
	grep "bank-info: ValueError: Could not find \"foo_user\"" nonexistent_user_passed.err
'

test_expect_success '-u displays all banks for a user' '
	flux account bank-info -u ${username} > bank_info_u.test1 &&
	grep "A" bank_info_u.test1 &&
	grep "C" bank_info_u.test1 &&
	flux account bank-info -u user1 > bank_info_u.test2 &&
	grep "A" bank_info_u.test2 &&
	flux account bank-info -u user2 > bank_info_u.test3 &&
	grep "B" bank_info_u.test3
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
