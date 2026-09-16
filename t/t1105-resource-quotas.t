#!/bin/bash

test_description='test the resource quotas jobtap plugin'

. `dirname $0`/sharness.sh

RESOURCE_QUOTAS=${FLUX_BUILD_DIR}/src/plugins/.libs/resource_quotas.so

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 2 job -Slog-stderr-level=1

test_expect_success 'load resource quotas plugin' '
	flux jobtap load ${RESOURCE_QUOTAS}
'

test_expect_success 'resource_quotas plugin shows up as loaded' '
	flux jobtap list | grep resource_quotas
'

test_expect_success 'a job can be submitted and completes with the plugin loaded' '
	job=$(flux submit -n1 true) &&
	flux job wait-event -t 30 ${job} clean
'

test_expect_success 'unload resource quotas plugin' '
	flux jobtap remove resource_quotas.so &&
	flux jobtap list > loaded.txt &&
	test_must_fail grep resource_quotas loaded.txt
'

test_expect_success 'plugin can be loaded again after being unloaded' '
	flux jobtap load ${RESOURCE_QUOTAS} &&
	flux jobtap list | grep resource_quotas
'

test_expect_success 'tracked usage is empty with no running jobs' '
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources == {}" <query.json
'

test_expect_success 'a running job shows up in tracked usage' '
	uid=$(id -u) &&
	job1=$(flux submit -N1 -n2 sleep 60) &&
	flux job wait-event -t 30 ${job1} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].node == 1" <query.json &&
	jq -e ".user_resources[\"${uid}\"].core == 2" <query.json &&
	jq -e ".user_resources[\"${uid}\"].slot == 2" <query.json
'

test_expect_success 'a second running job adds to tracked usage' '
	job2=$(flux submit -n1 sleep 60) &&
	flux job wait-event -t 30 ${job2} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].node == 2" <query.json &&
	jq -e ".user_resources[\"${uid}\"].core == 3" <query.json
'

test_expect_success 'jobs already running are counted when the plugin loads' '
	flux jobtap remove resource_quotas.so &&
	flux jobtap load ${RESOURCE_QUOTAS} &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].node == 2" <query.json &&
	jq -e ".user_resources[\"${uid}\"].core == 3" <query.json
'

test_expect_success 'a job that finishes is removed from tracked usage' '
	flux cancel ${job2} &&
	flux job wait-event -t 30 ${job2} clean &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].node == 1" <query.json &&
	jq -e ".user_resources[\"${uid}\"].core == 2" <query.json
'

test_expect_success 'tracked usage is empty once all jobs are inactive' '
	flux cancel ${job1} &&
	flux job wait-event -t 30 ${job1} clean &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources == {}" <query.json
'

test_expect_success 'a job canceled before it runs is never counted' '
	flux queue stop &&
	job3=$(flux submit -n1 sleep 60) &&
	flux job wait-event -t 30 ${job3} depend &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources == {}" <query.json &&
	flux cancel ${job3} &&
	flux job wait-event -t 30 ${job3} clean &&
	flux queue start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources == {}" <query.json
'

test_expect_success 'no quotas are configured by default' '
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".quotas.user == {}" <query.json &&
	jq -e ".held_jobs == {}" <query.json
'

test_expect_success 'per-user quotas are loaded from the broker config' '
	flux config load <<-EOF &&
	[accounting.quotas.user]
	node = 1
	quantum = 2
	EOF
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".quotas.user.node == 1" <query.json &&
	jq -e ".quotas.user.quantum == 2" <query.json
'

test_expect_success 'a negative quota is rejected on config reload' '
	test_must_fail flux config load <<-EOF 2>negative.err &&
	[accounting.quotas.user]
	node = -1
	EOF
	test_debug "cat negative.err" &&
	grep "must be a non-negative integer" negative.err
'

test_expect_success 'a non-integer quota is rejected on config reload' '
	test_must_fail flux config load <<-EOF 2>string.err &&
	[accounting.quotas.user]
	node = "one"
	EOF
	test_debug "cat string.err" &&
	grep "must be a non-negative integer" string.err
'

test_expect_success 'a quotas.user value that is not a table is rejected' '
	test_must_fail flux config load <<-EOF 2>table.err &&
	[accounting.quotas]
	user = 1
	EOF
	test_debug "cat table.err" &&
	grep "must be a table" table.err
'

test_expect_success 'quotas are unchanged after a rejected config reload' '
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".quotas.user.node == 1" <query.json &&
	jq -e ".quotas.user.quantum == 2" <query.json
'

test_expect_success 'a job requesting more than its quota is rejected' '
	test_must_fail flux submit -N2 true 2>reject.err &&
	test_debug "cat reject.err" &&
	grep "job requests 2 node but the per-user quota is 1" reject.err
'

test_expect_success 'a job that would exceed a quota is held' '
	job1=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job1} start &&
	job2=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job2} dependency-add &&
	flux jobs -no "{dependencies}" ${job2} | grep resource-quota-user &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".held_jobs[\"${uid}\"] == [$(flux job id ${job2})]" <query.json
'

test_expect_success 'a held job is released when a running job finishes' '
	flux cancel ${job1} &&
	flux job wait-event -t 30 ${job2} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".held_jobs == {}" <query.json &&
	jq -e ".user_resources[\"${uid}\"].node == 1" <query.json
'

test_expect_success 'held jobs are released in submission order' '
	job3=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job3} dependency-add &&
	job4=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job4} dependency-add &&
	flux cancel ${job2} &&
	flux job wait-event -t 30 ${job3} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".held_jobs[\"${uid}\"] == [$(flux job id ${job4})]" <query.json &&
	flux cancel ${job3} &&
	flux job wait-event -t 30 ${job4} start &&
	flux cancel ${job4} &&
	flux job wait-event -t 30 ${job4} clean
'

test_expect_success 'a job canceled while held is forgotten' '
	job5=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job5} start &&
	job6=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job6} dependency-add &&
	flux cancel ${job6} &&
	flux job wait-event -t 30 ${job6} clean &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".held_jobs == {}" <query.json
'

test_expect_success 'held jobs and quotas survive a plugin reload' '
	job7=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job7} dependency-add &&
	flux jobtap remove resource_quotas.so &&
	flux jobtap load ${RESOURCE_QUOTAS} &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".quotas.user.node == 1" <query.json &&
	jq -e ".held_jobs[\"${uid}\"] == [$(flux job id ${job7})]" <query.json &&
	flux cancel ${job5} &&
	flux job wait-event -t 30 ${job7} start
'

test_expect_success 'a held job is released on reload if usage dropped' '
	job8=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job8} dependency-add &&
	flux jobtap remove resource_quotas.so &&
	flux cancel ${job7} &&
	flux job wait-event -t 30 ${job7} clean &&
	flux jobtap load ${RESOURCE_QUOTAS} &&
	flux job wait-event -t 30 ${job8} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".held_jobs == {}" <query.json
'

test_expect_success 'raising a quota releases held jobs' '
	job9=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job9} dependency-add &&
	flux config load <<-EOF &&
	[accounting.quotas.user]
	node = 2
	quantum = 2
	EOF
	flux job wait-event -t 30 ${job9} start &&
	flux cancel ${job8} ${job9} &&
	flux job wait-event -t 30 ${job9} clean
'

test_expect_success 'a job requesting more of a custom resource than its quota is rejected' '
	flux run --dry-run -n1 true \
		| jq ".resources[0].with += [{\"type\": \"quantum\", \"count\": 3}]" \
		> quantum3.json &&
	test_must_fail flux job submit quantum3.json 2>quantum.err &&
	test_debug "cat quantum.err" &&
	grep "job requests 3 quantum but the per-user quota is 2" quantum.err
'

test_expect_success 'a running job with a custom resource type is tracked' '
	flux run --dry-run -n1 sleep 60 \
		| jq ".resources[0].with += [{\"type\": \"quantum\", \"count\": 2}]" \
		> quantum2.json &&
	job10=$(flux job submit quantum2.json) &&
	flux job wait-event -t 30 ${job10} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].quantum == 2" <query.json
'

test_expect_success 'a job that would exceed a custom resource quota is held' '
	flux run --dry-run -n1 sleep 60 \
		| jq ".resources[0].with += [{\"type\": \"quantum\", \"count\": 1}]" \
		> quantum1.json &&
	job11=$(flux job submit quantum1.json) &&
	flux job wait-event -t 30 ${job11} dependency-add &&
	flux cancel ${job10} &&
	flux job wait-event -t 30 ${job11} start &&
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".user_resources[\"${uid}\"].quantum == 1" <query.json &&
	flux cancel ${job11} &&
	flux job wait-event -t 30 ${job11} clean
'

test_expect_success 'quotas are removed by reloading a config without them' '
	flux config load <<-EOF &&
	[accounting.quotas.user]
	EOF
	flux jobtap query resource_quotas.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".quotas.user == {}" <query.json &&
	job12=$(flux submit -N2 true) &&
	flux job wait-event -t 30 ${job12} clean
'

test_expect_success 'a quotas value that is not a table is rejected' '
	test_must_fail flux config load <<-EOF 2>quotas.err &&
	[accounting]
	quotas = 5
	EOF
	test_debug "cat quotas.err" &&
	grep "failed to unpack accounting.quotas.user" quotas.err
'

test_expect_success 'a job whose resources cannot be counted is rejected' '
	flux run --dry-run -n1 true \
		| jq ".resources = [{\"type\": \"node\", \"count\": 1}]" \
		> noslot.json &&
	test_must_fail flux job submit noslot.json 2>noslot.err &&
	test_debug "cat noslot.err" &&
	grep "failed to count job resources" noslot.err
'

test_expect_success 'a held job whose resources cannot be counted gets an exception on reload' '
	job13=$(flux submit -N1 sleep 60) &&
	flux job wait-event -t 30 ${job13} start &&
	flux jobtap remove resource_quotas.so &&
	jq ".attributes.system.dependencies = \
		[{\"scheme\": \"afterany\", \"value\": \"${job13}\"}]" \
		noslot.json > noslot-dep.json &&
	job14=$(flux job submit noslot-dep.json) &&
	flux job wait-event -t 30 ${job14} dependency-add &&
	flux jobtap load ${RESOURCE_QUOTAS} &&
	flux job wait-event -t 30 ${job14} exception > exception.out &&
	test_debug "cat exception.out" &&
	grep "failed to count job resources" exception.out &&
	flux job wait-event -t 30 ${job14} clean &&
	flux cancel ${job13} &&
	flux job wait-event -t 30 ${job13} clean
'

test_done
