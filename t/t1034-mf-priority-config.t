#!/bin/bash

test_description='Test configuring weights of multi-factor priority factors'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'load plugin successfully without configuration' '
  	flux jobtap load ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'create a flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root bankA 1
'

test_expect_success 'add a user to the DB' '
	flux account -p ${DB_PATH} add-user --username=user1001 --userid=1001 --bank=bankA
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'no configured priority factors will use default weights' '
	job1=$(flux python ${SUBMIT_AS} 1001 -n1 hostname) &&
	flux job wait-event -f json $job1 priority | jq '.context.priority' > job1.test &&
	grep "50000" job1.test &&
	flux cancel $job1
'

test_expect_success 'set up new configuration for multi-factor priority plugin' '
	cat >config/test.toml <<-EOT &&
	[accounting.factor-weights]
	fairshare = 1000
	queue = 100
	EOT
	flux config reload
'

test_expect_success 'successfully submit a job with loaded configuration' '
	job2=$(flux python ${SUBMIT_AS} 1001 -n1 hostname) &&
	flux job wait-event -f json $job2 priority | jq '.context.priority' > job2.test &&
	grep "500" job2.test &&
	flux cancel $job2
'

test_expect_success 'change the configuration for the priority factors' '
	cat >config/test.toml <<-EOT &&
	[accounting.factor-weights]
	fairshare = 500
	queue = 100
	EOT
	flux config reload
'

test_expect_success 'successfully submit a job with the new configuration' '
	job3=$(flux python ${SUBMIT_AS} 1001 -n1 hostname) &&
	flux job wait-event -f json $job3 priority | jq '.context.priority' > job3.test &&
	grep "250" job3.test &&
	flux cancel $job3
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
