#!/bin/bash

test_description='test list-users command'

. `dirname $0`/sharness.sh
FLUX_ACCOUNTING_DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${FLUX_ACCOUNTING_DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${FLUX_ACCOUNTING_DB} -t
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze &&
	flux account add-queue silver &&
	flux account add-queue gold
'

test_expect_success 'add some projects to the DB' '
	flux account add-project leviathan_wakes &&
	flux account add-project babylons_gate
'

test_expect_success 'add some users to the DB' '
	flux account add-user --username=user1 --userid=5011 --bank=A &&
	flux account add-user --username=user2 --userid=5012 --bank=A &&
	flux account add-user --username=user2 --userid=5012 --bank=B &&
	flux account add-user --username=user3 --userid=5013 --bank=B &&
	flux account add-user --username=user4 --userid=5014 --bank=C
'

test_expect_success 'edit two associations to have different shares values than the rest' '
	flux account edit-user user3 --shares=100 &&
	flux account edit-user user4 --shares=100
'

test_expect_success 'edit associations to belong to different queues' '
	flux account edit-user user1 --queues="bronze" &&
	flux account edit-user user2 --queues="bronze,silver" &&
	flux account edit-user user3 --queues="bronze,silver,gold" &&
	flux account edit-user user4 --queues="bronze,silver"
'

test_expect_success 'edit associations to belong to different projects' '
	flux account edit-user user1 --projects="leviathan_wakes" &&
	flux account edit-user user2 \
		--bank=B \
		--projects="leviathan_wakes,babylons_gate" \
		--default-project="leviathan_wakes"
'

test_expect_success 'call list-users --help' '
	flux account list-users --help
'

test_expect_success 'pass in an invalid argument to list-users' '
	test_must_fail flux account list-users --foo=bar > invalid_arg.out 2>&1 &&
	grep "error: unrecognized arguments: --foo=bar" invalid_arg.out
'

# If no filters are passed, every association in the association_table will be
# returned in the output.
test_expect_success 'call list-users with no optional args to get all associations' '
	flux account list-users --json >all_users.json &&
	test_debug "jq -S . <all_users.json" &&
	jq -e "length == 5" all_users.json 
'

# We can also pass multiple conditions for each filter.
test_expect_success 'list users from both bank A and B' '
	flux account list-users --bank=A,B --json > multiple_banks.json &&
	jq -e "length == 4" multiple_banks.json
'

test_expect_success 'list users from multiple queues' '
	flux account list-users --queues=silver,gold --json > multiple_queues.json &&
	jq -e "length == 4" multiple_queues.json &&
	test_must_fail grep "user1" multiple_queues.json &&
	grep "user2" multiple_queues.json &&
	grep "user3" multiple_queues.json &&
	grep "user4" multiple_queues.json
'

# In the following set of tests, we pass certain filters to only get
# the associations which fit the criteria of the filters passed in.
test_expect_success 'filter associations by bank' '
	flux account list-users --json --bank=A >bankA_users.json &&
	test_debug "jq -S . <bankA_users.json" &&
	jq -e "length == 2" bankA_users.json 
'

test_expect_success 'filter associations by shares' '
	flux account list-users --json --shares=100 >100shares_users.json &&
	test_debug "jq -S . <100shares_users.json" &&
	jq -e "length == 2" 100shares_users.json 
'

test_expect_success 'filter associations by queues' '
	flux account list-users --json --queues="bronze" >bronze_users.json &&
	test_debug "jq -S . <bronze_users.json" &&
	jq -e "length == 5" bronze_users.json
'

test_expect_success 'filter associations by more queues' '
	flux account list-users --json --queues="gold" >gold_users.json &&
	test_debug "jq -S . <gold_users.json" &&
	jq -e "length == 1" gold_users.json
'

test_expect_success 'filter associations by project' '
	flux account list-users --json --project="leviathan_wakes" >leviathan_wakes_users.json &&
	test_debug "jq -S . <leviathan_wakes_users.json" &&
	jq -e "length == 2" leviathan_wakes_users.json
'

test_expect_success 'delete an association and ensure we can filter by active status' '
	flux account delete-user user4 C &&
	flux account list-users --json --active=0 >inactive_users.json &&
	test_debug "jq -S . <inactive_users.json" &&
	jq -e "length == 1" inactive_users.json
'

# In the following test, we pass more than one field when listing the
# associations to further filter the values returned.
test_expect_success 'filter by more than one field' '
	flux account list-users --json --bank=A --projects="leviathan_wakes" >multiple_filters_users.json &&
	cat multiple_filters_users.json &&
	test_debug "jq -S . <multiple_filters_users.json" &&
	jq -e "length == 1" multiple_filters_users.json
'

# In the following set of tests, we customize the output to only include
# certain columns in the output.
test_expect_success 'customize JSON output of list-users' '
	flux account list-users --json \
		--bank=A --fields=username,bank,default_bank,shares > bankA_custom_output.json &&
	grep "\"username\": \"user1\"" bankA_custom_output.json &&
	grep "\"username\": \"user2\"" bankA_custom_output.json
'

test_expect_success 'customize table output of list-users' '
	flux account list-users \
		--bank=A --fields=username,bank,default_bank,shares > bankA_custom_table.out &&
	grep "user1" bankA_custom_table.out &&
	grep "user2" bankA_custom_table.out
'

# In the following test, we customize the output with a format string.
test_expect_success 'customize output using a format string' '
	flux account list-users -o "{username:<8}||{userid:<6}|{bank:<7}|" > format_string.out &&
	grep "username||userid|bank   |" format_string.out &&
	grep "user1   ||5011  |A      |" format_string.out
'

test_expect_success 'call list-users and pass --default-project' '
	flux account list-users \
		-o "{username:<8}||{userid:<6}|{bank:<7}|{default_project:<16}" \
		--default-project="leviathan_wakes" > default_project.out &&
	grep "user2   ||5012  |B      |leviathan_wakes" default_project.out
'

test_expect_success 'remove flux-accounting DB' '
	rm ${FLUX_ACCOUNTING_DB}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
