#!/bin/bash

test_description='test commands interacting with config_table'

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

test_expect_success 'add-config --help works' '
	flux account add-config --help
'

test_expect_success 'add a key-value pair to config_table' '
	flux account add-config foo=bar
'

test_expect_success 'trying to add a duplicate key raises IntegrityError' '
	test_must_fail flux account add-config foo=bar > duplicate_key.out 2>&1 &&
	grep "IntegrityError: UNIQUE constraint failed: config_table.key" duplicate_key.out
'

test_expect_success 'key-value pair with a bad format raises ValueError' '
	test_must_fail flux account add-config bad=format=foo > bad_format.out 2>&1 &&
	grep "ValueError: key-value string must contain exactly one \"=\"" bad_format.out
'

test_expect_success 'view a key-value pair from config_table' '
	flux account view-config foo > view_config_test1.out &&
	grep "key | value" view_config_test1.out &&
	grep "foo | bar " view_config_test1.out
'

test_expect_success 'view a key-value pair from config_table with JSON' '
	flux account view-config foo --json > view_config_test2.out &&
	grep "\"key\": \"foo\"" view_config_test2.out &&
	grep "\"value\": \"bar\"" view_config_test2.out
'

test_expect_success 'view a key-value pair from config_table with format string' '
	flux account view-config foo -o "{key}->{value}"> view_config_test3.out &&
	grep "key->value" view_config_test3.out &&
	grep "foo->bar" view_config_test3.out
'

test_expect_success 'editing priority_usage_reset_period with a bad value raises error' '
	test_must_fail flux account edit-config \
		priority_usage_reset_period=foo > edit_config_bad.out 2>&1 &&
	grep "edit-config: ValueError: invalid Flux standard duration" edit_config_bad.out
'

test_expect_success 'editing a key-value pair that does not exist raises error' '
	test_must_fail flux account \
		edit-config i_dont_exist=foo > edit_config_bad_2.out 2>&1 &&
	grep "edit-config: ValueError: key i_dont_exist not found in config_table" edit_config_bad_2.out
'

test_expect_success 'edit multiple key-value pairs at the same time' '
	flux account add-config key1=value1 &&
	flux account add-config key2=value2 &&
	flux account edit-config key1=foo1 key2=foo2 &&
	flux account list-configs > edited_configs.out &&
	grep "key1                        | foo1" edited_configs.out &&
	grep "key2                        | foo2" edited_configs.out
'

test_expect_success 'delete a key from config_table' '
	flux account delete-config foo &&
	test_must_fail flux account view-config foo > view_config_noexist.err 2>&1 &&
	grep "ValueError: key foo not found in config_table" view_config_noexist.err
'

test_expect_success 'trying to delete priority_usage_reset_period does not work' '
	test_must_fail flux account \
		delete-config priority_usage_reset_period > no_delete1.err 2>&1 &&
	grep "ValueError: key-value pair is not allowed to be removed from config_table" no_delete1.err
'

test_expect_success 'trying to delete priority_decay_half_life does not work' '
	test_must_fail flux account \
		delete-config priority_decay_half_life > no_delete2.err 2>&1 &&
	grep "ValueError: key-value pair is not allowed to be removed from config_table" no_delete2.err
'

test_expect_success 'trying to delete decay_factor does not work' '
	test_must_fail flux account \
		delete-config decay_factor > no_delete3.err 2>&1 &&
	grep "ValueError: key-value pair is not allowed to be removed from config_table" no_delete3.err
'

test_expect_success 'list all configs in config_table' '
	flux account list-configs > list_configs.test &&
	cat <<-EOF >list_configs.expected &&
	key                         | value  
	----------------------------+--------
	priority_usage_reset_period | 2419200
	priority_decay_half_life    | 604800 
	decay_factor                | 0.5    
	node_weight                 | 1.0    
	core_weight                 | 0.0    
	gpu_weight                  | 0.0    
	key1                        | foo1   
	key2                        | foo2   
	EOF
	test_cmp list_configs.test list_configs.expected
'

test_expect_success 'list all configs in config_table in JSON format' '
	flux account list-configs --json > list_configs_json.test &&
	grep "\"key\": \"priority_usage_reset_period\"" list_configs_json.test &&
	grep "\"value\": \"2419200\"" list_configs_json.test &&
	grep "\"key\": \"priority_decay_half_life\"" list_configs_json.test &&
	grep "\"value\": \"604800\"" list_configs_json.test &&
	grep "\"key\": \"decay_factor\"" list_configs_json.test &&
	grep "\"value\": \"0.5\"" list_configs_json.test
'

test_expect_success 'list all configs with --fields' '
	flux account list-configs --fields=key > keys.test &&
	cat keys.test &&
	cat <<-EOF >keys.expected &&
	key                        
	---------------------------
	core_weight                
	decay_factor               
	gpu_weight                 
	key1                       
	key2                       
	node_weight                
	priority_decay_half_life   
	priority_usage_reset_period
	EOF
	test_cmp keys.test keys.expected
'

test_expect_success 'list all configs with format string' '
	flux account list-configs -o "{key}->{value}" > list_configs_format.test &&
	cat list_configs_format.test &&
	cat <<-EOF >list_configs_format.expected &&
	key->value
	priority_usage_reset_period->2419200
	priority_decay_half_life->604800
	decay_factor->0.5
	node_weight->1.0
	core_weight->0.0
	gpu_weight->0.0
	key1->foo1
	key2->foo2
	EOF
	test_cmp list_configs_format.test list_configs_format.expected
'

test_expect_success 'edit the usage parameters successfully' '
	flux account edit-config \
		priority_decay_half_life=15m \
		priority_usage_reset_period=1h \
		decay_factor=0.2 &&
	flux account list-configs -o "{key}->{value}" > edit_usage_configs.test &&
	grep "priority_decay_half_life->900" edit_usage_configs.test &&
	grep "priority_usage_reset_period->3600" edit_usage_configs.test &&
	grep "decay_factor->0.2" edit_usage_configs.test
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
