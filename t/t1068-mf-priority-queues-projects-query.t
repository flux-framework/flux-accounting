#!/bin/bash

test_description='test fetching queue and project information in flux jobtap query'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
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

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root bankA 1
'

test_expect_success 'add an association' '
	flux account add-user --username=user1 --userid=50001 --bank=bankA
'

test_expect_success 'add some queues' '
	flux account add-queue bronze --priority=100 &&
	flux account add-queue silver --priority=200 &&
	flux account add-queue gold --priority=300
'

test_expect_success 'add some projects' '
	flux account add-project project1 &&
	flux account add-project project2 &&
	flux account add-project project3 &&
	flux account add-project project4
'

test_expect_success 'send flux-accounting data to plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'run flux jobtap query' '
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq
'

test_expect_success 'check queue information in output of flux jobtap query' '
	jq -e ".queues.bronze.priority == 100" <query.json &&
	jq -e ".queues.silver.priority == 200" <query.json &&
	jq -e ".queues.gold.priority == 300" <query.json
'

test_expect_success 'check projects information in output of flux jobtap query' '
	jq -e ".projects | length == 5" <query.json &&
	jq -e ".projects[0] == \"*\"" <query.json &&
	jq -e ".projects[1] == \"project1\"" <query.json &&
	jq -e ".projects[2] == \"project2\"" <query.json &&
	jq -e ".projects[3] == \"project3\"" <query.json &&
	jq -e ".projects[4] == \"project4\"" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
