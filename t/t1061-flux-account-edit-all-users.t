#!/bin/bash

test_description='test the edit-all-users command'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add a queue' '
	flux account add-queue bronze
'

test_expect_success 'add a project' '
	flux account add-project physics
'

test_expect_success 'add some associations' '
	flux account add-user --username=user1 --bank=A &&
	flux account add-user --username=user2 --bank=A &&
	flux account add-user --username=user3 --bank=A
'

test_expect_success 'list all associations' '
	flux account list-users -o "{username:<8} | {bank:<8}" > users.default &&
	grep "username | bank" users.default &&
	grep "user1    | A" users.default &&
	grep "user2    | A" users.default &&
	grep "user3    | A" users.default
'

test_expect_success 'call edit-all-users with no args passed; make sure ValueError is raised' '
	test_must_fail flux account edit-all-users > no_args.error 2>&1 &&
	grep "edit-all-users: ValueError: no fields provided for update" no_args.error
'

test_expect_success 'call edit-all-users with an invalid field' '
	test_must_fail flux account edit-all-users --foo=bar > bad_arg.error 2>&1 &&
	grep "unrecognized arguments: --foo=bar" bad_arg.error
'

test_expect_success 'edit the bank for every association' '
	flux account edit-all-users --bank=B &&
	flux account list-users -o "{username:<8} | {bank:<8}" > new_bank.test &&
	grep "username | bank" new_bank.test &&
	grep "user1    | B" new_bank.test &&
	grep "user2    | B" new_bank.test &&
	grep "user3    | B" new_bank.test
'

test_expect_success 'edit the default bank for every association' '
	flux account edit-all-users --default-bank=B &&
	flux account list-users -o "{username:<8} | {default_bank:<8}" > new_default_bank.test &&
	grep "username | default_bank" new_default_bank.test &&
	grep "user1    | B" new_default_bank.test &&
	grep "user2    | B" new_default_bank.test &&
	grep "user3    | B" new_default_bank.test
'

test_expect_success 'edit the shares for every association' '
	flux account edit-all-users --shares=100 &&
	flux account list-users -o "{username:<8} | {shares:<8}" > new_shares.test &&
	grep "username | shares" new_shares.test &&
	grep "user1    | 100" new_shares.test &&
	grep "user2    | 100" new_shares.test &&
	grep "user3    | 100" new_shares.test
'

test_expect_success 'edit the fair-share for every association' '
	flux account edit-all-users --fairshare=0.75 &&
	flux account list-users -o "{username:<8} | {fairshare:<8}" > new_fairshare.test &&
	grep "username | fairshare" new_fairshare.test &&
	grep "user1    | 0.75" new_fairshare.test &&
	grep "user2    | 0.75" new_fairshare.test &&
	grep "user3    | 0.75" new_fairshare.test
'

test_expect_success 'edit the max-running-jobs for every association' '
	flux account edit-all-users --max-running-jobs=100 &&
	flux account list-users -o "{username:<8} | {max_running_jobs:<8}" > new_max_run_jobs.test &&
	grep "username | max_running_jobs" new_max_run_jobs.test &&
	grep "user1    | 100" new_max_run_jobs.test &&
	grep "user2    | 100" new_max_run_jobs.test &&
	grep "user3    | 100" new_max_run_jobs.test
'

test_expect_success 'edit the max-active-jobs for every association' '
	flux account edit-all-users --max-active-jobs=200 &&
	flux account list-users -o "{username:<8} | {max_active_jobs:<8}" > new_max_active_jobs.test &&
	grep "username | max_active_jobs" new_max_active_jobs.test &&
	grep "user1    | 200" new_max_active_jobs.test &&
	grep "user2    | 200" new_max_active_jobs.test &&
	grep "user3    | 200" new_max_active_jobs.test
'

test_expect_success 'edit the max-nodes for every association' '
	flux account edit-all-users --max-nodes=100 &&
	flux account list-users -o "{username:<8} | {max_nodes:<8}" > new_max_nodes.test &&
	grep "username | max_nodes" new_max_nodes.test &&
	grep "user1    | 100" new_max_nodes.test &&
	grep "user2    | 100" new_max_nodes.test &&
	grep "user3    | 100" new_max_nodes.test
'

test_expect_success 'edit the max-cores for every association' '
	flux account edit-all-users --max-cores=1000 &&
	flux account list-users -o "{username:<8} | {max_cores:<8}" > new_max_cores.test &&
	grep "username | max_cores" new_max_cores.test &&
	grep "user1    | 1000" new_max_cores.test &&
	grep "user2    | 1000" new_max_cores.test &&
	grep "user3    | 1000" new_max_cores.test
'

test_expect_success 'edit the queues for every association' '
	flux account edit-all-users --queues="bronze" &&
	flux account list-users -o "{username:<8} | {queues:<8}" > new_queues.test &&
	grep "username | queues" new_queues.test &&
	grep "user1    | bronze" new_queues.test &&
	grep "user2    | bronze" new_queues.test &&
	grep "user3    | bronze" new_queues.test
'

test_expect_success 'edit the projects for every association' '
	flux account edit-all-users --projects="physics" &&
	flux account list-users -o "{username:<8} | {projects:<8}" > new_projects.test &&
	grep "username | projects" new_projects.test &&
	grep "user1    | physics" new_projects.test &&
	grep "user2    | physics" new_projects.test &&
	grep "user3    | physics" new_projects.test
'

test_expect_success 'edit the default project for every association' '
	flux account edit-all-users --default-project="physics" &&
	flux account list-users -o "{username:<8} | {default_project:<8}" > new_default_project.test &&
	grep "username | default_project" new_default_project.test &&
	grep "user1    | physics" new_default_project.test &&
	grep "user2    | physics" new_default_project.test &&
	grep "user3    | physics" new_default_project.test
'

test_expect_success 'edit multiple fields at once for every association' '
	flux account edit-all-users --bank=A --max-nodes=123 &&
	flux account list-users -o "{username:<8} | {bank:<8} | {max_nodes:<8}" > multiple_fields.test &&
	grep "username | bank     | max_nodes" multiple_fields.test &&
	grep "user1    | A        | 123" multiple_fields.test &&
	grep "user2    | A        | 123" multiple_fields.test &&
	grep "user3    | A        | 123" multiple_fields.test
'

test_expect_success 'reset a field for every association' '
	flux account edit-all-users --max-cores=-1 &&
	flux account list-users -o "{username:<8} | {max_cores:<8}" > reset_max_cores.test &&
	grep "username | max_cores" reset_max_cores.test &&
	grep "user1    | 2147483647" reset_max_cores.test &&
	grep "user2    | 2147483647" reset_max_cores.test &&
	grep "user3    | 2147483647" reset_max_cores.test
'

test_expect_success 'reset the "projects" column for every association' '
	flux account edit-all-users --projects=-1 &&
	flux account list-users -o "{username:<8} | {projects:<8}" > projects_edited.test &&
	grep "username | projects" projects_edited.test &&
	grep "user1    | *" projects_edited.test &&
	grep "user2    | *" projects_edited.test &&
	grep "user3    | *" projects_edited.test
'

test_expect_success 'reset the "queues" column for every association' '
	flux account edit-all-users --queues=-1 &&
	flux account list-users -o "{username:<8} | {queues:<8}" > queues_edited.test &&
	grep "username | queues" queues_edited.test &&
	grep "user1    | " queues_edited.test &&
	grep "user2    | " queues_edited.test &&
	grep "user3    | " queues_edited.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
