#!/bin/bash

test_description='Test multi-factor priority plugin with age factor enabled'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'load plugin successfully without configuration' '
  flux jobtap load ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'create a flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
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

test_expect_success 'no configured priority factors will use default weights, including age' '
	job1=$(flux python ${SUBMIT_AS} 1001 -n1 hostname) &&
	flux job wait-event -f json $job1 priority | jq '.context.priority' > job1.test &&
  cat job1.test &&
	grep -c "50[0-9][0-9][0-9]" job1.test &&
	flux job cancel $job1
'

test_done
