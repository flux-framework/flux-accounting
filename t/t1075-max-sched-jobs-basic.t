#!/bin/bash

test_description='test managing the max-sched-jobs property'

. `dirname $0`/sharness.sh

mkdir -p config

DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'define max-sched-jobs property when adding association' '
	flux account add-user \
		--username=user1 --bank=A --userid=50001 --max-sched-jobs=10
'

test_expect_success 'view-user: max-sched-jobs property shows up in view-user' '
	flux account view-user user1 > view_user1.out &&
	grep "\"max_sched_jobs\": 10" view_user1.out
'

test_expect_success 'view-user: max-sched-jobs property shows up in view-user --parsable' '
	flux account view-user user1 --parsable > view_user2.out &&
	grep "max_sched_jobs" view_user2.out
'

test_expect_success 'view-user: max-sched-jobs property can be specified in --fields' '
	flux account view-user user1 --fields=username,max_sched_jobs > view_user3.out &&
	grep "\"max_sched_jobs\": 10" view_user3.out
'

test_expect_success 'view-user: max-sched-jobs property can be in format string' '
	flux account view-user user1 -o "{username:<8} | {max_sched_jobs:<15}" > view_user4.out &&
	grep "max_sched_jobs" view_user4.out
'

test_expect_success 'list-users: max-sched-jobs property shows up under list-users' '
	flux account list-users > list_users1.out &&
	grep "max_sched_jobs" list_users1.out
'

test_expect_success 'list-users: max-sched-jobs property can be specified in --fields' '
	flux account list-users --fields=username,max_sched_jobs > list_users2.out &&
	grep "max_sched_jobs" list_users2.out
'

test_expect_success 'list-users: max-sched-jobs property can be in format string' '
	flux account list-users -o "{username:<8} | {max_sched_jobs:<15}" > list_users3.out &&
	grep "max_sched_jobs" list_users3.out
'

test_expect_success 'list-users: max-sched-jobs property can be filtered' '
	flux account list-users --max-sched-jobs=10 > list_users4.out &&
	grep "user1" list_users4.out
'

test_expect_success 'edit-user: max-sched-jobs property can be edited' '
	flux account edit-user user1 --max-sched-jobs=20 &&
	flux account view-user user1 > edit_user1.out &&
	grep "\"max_sched_jobs\": 20" edit_user1.out
'

test_expect_success 'edit-user: max-sched-jobs property can be reset' '
	flux account edit-user user1 --max-sched-jobs=-1 &&
	flux account view-user user1 > edit_user2.out &&
	grep "\"max_sched_jobs\": \"unlimited\"" edit_user2.out
'

test_expect_success 'edit-all-users: max-sched-jobs property can be edited' '
	flux account edit-all-users --max-sched-jobs=100 &&
	flux account view-user user1 > edit_user3.out &&
	grep "\"max_sched_jobs\": 100" edit_user3.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
