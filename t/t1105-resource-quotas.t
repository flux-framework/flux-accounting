#!/bin/bash

test_description='test the resource quotas jobtap plugin'

. `dirname $0`/sharness.sh

RESOURCE_QUOTAS=${FLUX_BUILD_DIR}/src/plugins/.libs/resource_quotas.so

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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

test_done
