#!/bin/bash

test_description='test configuring priority factor weights in flux-accounting DB'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'view information about a particular priority factor' '
	flux account view-factor fairshare > fairshare.default &&
	grep "fairshare | 100000" fairshare.default
'

test_expect_success 'view information about a particular priority factor in JSON format' '
	flux account view-factor fairshare --json > fairshare.json &&
	grep "\"factor\": \"fairshare\"" fairshare.json &&
	grep "\"weight\": 100000" fairshare.json
'

test_expect_success 'view information about a particular priority factor with a format string' '
	flux account view-factor fairshare -o "|{weight:<8}||{factor:<10}|" > fairshare.format_string &&
	grep "|100000  ||fairshare |" fairshare.format_string
'

test_expect_success 'view information about a priority factor that does not exist' '
	test_must_fail flux account view-factor foo > factor.noexist 2>&1 &&
	grep "factor foo not found in priority_factor_weight_table" factor.noexist
'

test_expect_success 'edit the weight for a priority factor' '
	flux account edit-factor --factor=fairshare --weight=999 &&
	flux account view-factor fairshare > fairshare.edited &&
	grep "fairshare | 999" fairshare.edited
'

test_expect_success 'edit weight for a priority factor with a bad type' '
	test_must_fail flux account edit-factor \
		--factor=fairshare --weight=foo > fairshare.bad_type 2>&1 &&
	grep "edit-factor: error: argument --weight: invalid int value:" fairshare.bad_type
'

test_expect_success 'edit weight for a priority factor that does not exist' '
	test_must_fail flux account edit-factor \
		--factor=foo --weight=999 > fairshare_edit.noexist 2>&1 &&
	grep "factor foo not found in priority_factor_weight_table;" fairshare_edit.noexist &&
	grep "available factors are fairshare,queue,bank" fairshare_edit.noexist
'

test_expect_success 'list all of the priority factors' '
	flux account list-factors > list_factors.default &&
	grep "fairshare | 999" list_factors.default &&
	grep "queue     | 10000" list_factors.default &&
	grep "bank      | 0" list_factors.default
'

test_expect_success 'list all of the priority factors in JSON format' '
	flux account list-factors --json > list_factors.json &&
	grep "\"factor\": \"fairshare\"" list_factors.json &&
	grep "\"weight\": 999" list_factors.json &&
	grep "\"factor\": \"queue\"" list_factors.json &&
	grep "\"weight\": 10000" list_factors.json &&
	grep "\"factor\": \"bank\"" list_factors.json &&
	grep "\"weight\": 0" list_factors.json
'

test_expect_success 'edit the other two factors to have non-default weights' '
	flux account edit-factor --factor=queue --weight=50 &&
	flux account edit-factor --factor=bank --weight=1 &&
	flux account list-factors --json > list_factors_edited.json &&
	grep "\"weight\": 50" list_factors_edited.json &&
	grep "\"weight\": 1" list_factors_edited.json
'

test_expect_success 'reset the priority factors and their weights' '
	flux account reset-factors &&
	flux account list-factors > list_factors.reset &&
	grep "fairshare | 100000" list_factors.reset &&
	grep "queue     | 10000" list_factors.reset &&
	grep "bank      | 0" list_factors.reset
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
