#!/bin/bash

test_description='test submitting jobs as instance owner'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
ACCOUNTING_DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB, start flux-accounting service' '
	flux account -p ${ACCOUNTING_DB} create-db &&
	flux account-service -p ${ACCOUNTING_DB} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'send flux-accounting information to plugin' '
	flux account-priority-update -p ${ACCOUNTING_DB}
'

test_expect_success 'submit a job as instance owner' '
	username=$(whoami) &&
	uid=$(id -u) &&
	job=$(flux python ${SUBMIT_AS} ${uid} hostname) &&
	flux job wait-event -vt 5 ${job} alloc &&
	flux cancel ${job}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_expect_success 'remove flux-accounting DB' '
	rm ${ACCOUNTING_DB}
'

test_done
