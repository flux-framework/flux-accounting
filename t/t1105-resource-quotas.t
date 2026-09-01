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

test_done
