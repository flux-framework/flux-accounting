#!/bin/bash

test_description='Test flux account-priority-update command with flux-accounting DB and plugin'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'disable age factor in multi-factor priority plugin' '
	cat >config/test.toml <<-EOT &&
	[priority_factors]
	age_weight = 0
	EOT
	flux config reload
'

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account1 1
'

test_expect_success 'add some users to the DB' '
	flux account -p ${DB_PATH} add-user --username=user5011 --userid=5011 --bank=account1 &&
	flux account -p ${DB_PATH} add-user --username=user5012 --userid=5012 --bank=account1 &&
	flux account -p ${DB_PATH} add-user --username=user5013 --userid=5013 --bank=account1
'

test_expect_success 'add a queue to the DB' '
	flux account -p ${DB_PATH} add-queue default --priority=0
'

test_expect_success 'send the user information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'successfully submit jobs as each user' '
	jobid1=$(flux python ${SUBMIT_AS} 5011 hostname) &&
	jobid2=$(flux python ${SUBMIT_AS} 5012 hostname) &&
	jobid3=$(flux python ${SUBMIT_AS} 5013 hostname) &&
	flux jobs -A | grep "$jobid1\|$jobid2\|$jobid3"
'

test_done
