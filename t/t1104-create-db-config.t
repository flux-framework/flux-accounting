#!/bin/bash

test_description='test creating the flux-accounting database with a TOML config file'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
CUSTOM_DB_PATH=$(pwd)/FluxAccountingTestCustom.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

# get a value from config_table
# arg1 - database path
# arg2 - key
get_config_value() {
	local dbpath=$1
	local key=$2
	query="select value from config_table where key='${key}';"

	${QUERYCMD} -t 100 ${dbpath} "${query}" | awk -F' = ' '{print $2}'
}

# get a priority factor weight from priority_factor_weight_table
# arg1 - database path
# arg2 - factor
get_factor_weight() {
	local dbpath=$1
	local factor=$2
	query="select weight from priority_factor_weight_table where factor='${factor}';"

	${QUERYCMD} -t 100 ${dbpath} "${query}" | awk -F' = ' '{print $2}'
}

test_expect_success 'create a config file that customizes some defaults' '
	cat >accounting.toml <<-EOF
	[accounting.usage]
	decay-half-life = "14d"
	decay-factor = 0.8

	[accounting.usage.weights]
	core = 1.0

	[accounting.priority.factors]
	fairshare = 999

	[accounting.queues]
	deny-unknown = true
	EOF
'

test_expect_success 'create a flux-accounting DB with the config file' '
	flux account -p ${CUSTOM_DB_PATH} create-db --config-path=accounting.toml
'

test_expect_success 'configured values are seeded into config_table' '
	test $(get_config_value ${CUSTOM_DB_PATH} priority_decay_half_life) = "1209600" &&
	test $(get_config_value ${CUSTOM_DB_PATH} decay_factor) = "0.8" &&
	test $(get_config_value ${CUSTOM_DB_PATH} core_weight) = "1.0" &&
	test $(get_config_value ${CUSTOM_DB_PATH} deny_unknown_queues) = "true"
'

test_expect_success 'unconfigured values keep their defaults' '
	test $(get_config_value ${CUSTOM_DB_PATH} priority_usage_reset_period) = "2419200" &&
	test $(get_config_value ${CUSTOM_DB_PATH} node_weight) = "1.0" &&
	test $(get_config_value ${CUSTOM_DB_PATH} gpu_weight) = "0.0"
'

test_expect_success 'configured factor weights are seeded; others keep defaults' '
	test $(get_factor_weight ${CUSTOM_DB_PATH} fairshare) = "999" &&
	test $(get_factor_weight ${CUSTOM_DB_PATH} queue) = "10000" &&
	test $(get_factor_weight ${CUSTOM_DB_PATH} bank) = "0" &&
	test $(get_factor_weight ${CUSTOM_DB_PATH} urgency) = "1000"
'

test_expect_success 'command-line options take precedence over the config file' '
	flux account -p $(pwd)/precedence.db create-db \
		--config-path=accounting.toml --priority-decay-half-life=1d &&
	test $(get_config_value $(pwd)/precedence.db priority_decay_half_life) = "86400.0"
'

test_expect_success 'creating a DB without a config file uses the defaults' '
	flux account -p ${DB_PATH} create-db &&
	test $(get_config_value ${DB_PATH} priority_decay_half_life) = "604800" &&
	test $(get_config_value ${DB_PATH} priority_usage_reset_period) = "2419200" &&
	test $(get_config_value ${DB_PATH} decay_factor) = "0.5" &&
	test $(get_config_value ${DB_PATH} deny_unknown_queues) = "false" &&
	test $(get_factor_weight ${DB_PATH} fairshare) = "100000"
'

test_expect_success 'create-db fails with an unknown key in [accounting.usage]' '
	cat >bad_key.toml <<-EOF
	[accounting.usage]
	foo = 1
	EOF
	test_must_fail flux account -p $(pwd)/bad.db create-db --config-path=bad_key.toml
'

test_expect_success 'create-db fails with an unknown resource type' '
	cat >bad_resource.toml <<-EOF
	[accounting.usage.weights]
	quantum = 5.0
	EOF
	test_must_fail flux account -p $(pwd)/bad.db create-db --config-path=bad_resource.toml
'

test_expect_success 'create-db fails with an unknown priority factor' '
	cat >bad_factor.toml <<-EOF
	[accounting.priority.factors]
	foo = 1
	EOF
	test_must_fail flux account -p $(pwd)/bad.db create-db --config-path=bad_factor.toml
'

test_expect_success 'create-db fails with an out-of-range decay factor' '
	cat >bad_decay.toml <<-EOF
	[accounting.usage]
	decay-factor = 1.5
	EOF
	test_must_fail flux account -p $(pwd)/bad.db create-db --config-path=bad_decay.toml
'

test_expect_success 'create-db fails with a nonexistent config file' '
	test_must_fail flux account -p $(pwd)/bad.db create-db --config-path=nonexistent.toml
'

test_done
