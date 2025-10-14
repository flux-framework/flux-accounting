#!/bin/bash

test_description='test flux-account commands that require administrator privileges'

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

test_expect_success 'add-user should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account add-user --username=ohtani --bank=A > no_access_add-user.out 2>&1 &&
		grep "Request requires owner credentials" no_access_add-user.out
	)
'

test_expect_success 'delete-user should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account delete-user ohtani A > no_access_delete-user.out 2>&1 &&
		grep "Request requires owner credentials" no_access_delete-user.out
	)
'

test_expect_success 'edit-user should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account edit-user --max-active-jobs=100000 ohtani > no_access_edit-user.out 2>&1 &&
		grep "Request requires owner credentials" no_access_edit-user.out
	)
'

test_expect_success 'add-bank should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account add-bank --parent-bank=root H 1 > no_access_add-bank.out 2>&1 &&
		grep "Request requires owner credentials" no_access_add-bank.out
	)
'

test_expect_success 'delete-bank should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account delete-bank H > no_access_delete-bank.out 2>&1 &&
		grep "Request requires owner credentials" no_access_delete-bank.out
	)
'

test_expect_success 'edit-bank should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account edit-bank H --shares=12345 > no_access_edit-bank.out 2>&1 &&
		grep "Request requires owner credentials" no_access_edit-bank.out
	)
'

test_expect_success 'add-queue should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account add-queue queue_6 > no_access_add-queue.out 2>&1 &&
		grep "Request requires owner credentials" no_access_add-queue.out
	)
'

test_expect_success 'delete-queue should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account delete-queue queue_6 > no_access_delete-queue.out 2>&1 &&
		grep "Request requires owner credentials" no_access_delete-queue.out
	)
'

test_expect_success 'edit-queue should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account edit-queue queue_6 --priority=12345 > no_access_edit-queue.out 2>&1 &&
		grep "Request requires owner credentials" no_access_edit-queue.out
	)
'

test_expect_success 'add-project should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account add-project project_6 > no_access_add-project.out 2>&1 &&
		grep "Request requires owner credentials" no_access_add-project.out
	)
'

test_expect_success 'delete-project should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account delete-project project_3 > no_access_delete-project.out 2>&1 &&
		grep "Request requires owner credentials" no_access_delete-project.out
	)
'

test_expect_success 'scrub-old-jobs should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account scrub-old-jobs > no_access_scrub_old_jobs.out 2>&1 &&
		grep "Request requires owner credentials" no_access_scrub_old_jobs.out
	)
'

test_expect_success 'export-db should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		test_must_fail flux account export-db > no_access_export_db.out 2>&1 &&
		grep "Request requires owner credentials" no_access_export_db.out
	)
'

test_expect_success 'pop-db should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		touch users.csv &&
		test_must_fail flux account pop-db -c association_table.csv > no_access_pop_db.out 2>&1 &&
		grep "Request requires owner credentials" no_access_pop_db.out
	)
'

test_expect_success 'edit-factor should not be accessible by all users' '
	newid=$(($(id -u)+1)) &&
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$newid &&
		touch users.csv &&
		touch banks.csv &&
		test_must_fail flux account edit-factor --factor=bank --weight=999 > no_access_edit_factor.out 2>&1 &&
		grep "Request requires owner credentials" no_access_edit_factor.out
	)
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
