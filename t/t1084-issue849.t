#!/bin/bash

test_description='make sure data stored in the plugin is cleared on reload'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add two associations to the DB' '
	flux account add-user --username=user1 --userid=50001 --bank=A &&
	flux account add-user --username=user2 --userid=50002 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'both associations exist in plugin map' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e "[.mf_priority_map[] | select(.userid == 50001)] | length == 1" <query.json &&
	jq -e "[.mf_priority_map[] | select(.userid == 50002)] | length == 1" <query.json
'

test_expect_success 'remove second association from database' '
	flux account delete-user --force user2 A &&
	test_must_fail flux account view-user user2 > association_noexist.err 2>&1 &&
	grep "user user2 not found in association_table" association_noexist.err
'

test_expect_success 'unload and reload mf_priority.so with flux-accounting data' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'only user1 exists in plugin map' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e "[.mf_priority_map[] | select(.userid == 50001)] | length == 1" <query.json &&
	jq -e "[.mf_priority_map[] | select(.userid == 50002)] | length == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
