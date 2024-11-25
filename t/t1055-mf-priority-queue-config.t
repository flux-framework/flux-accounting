#!/bin/bash

test_description='test configuring priorities of queues in priority plugin'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'load priority plugin' '
  	flux jobtap load ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'create a flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root bankA 1
'

test_expect_success 'add some queues to the DB with configured priorities' '
	flux account add-queue bronze --priority=100 &&
	flux account add-queue silver --priority=500 &&
	flux account add-queue gold --priority=1000
'

test_expect_success 'add a user to the DB' '
	flux account add-user \
		--username=user5001 \
		--userid=5001 \
		--bank=bankA \
		--queues=bronze,silver
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'configure flux with queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload &&
	flux queue stop --all
'

test_expect_success 'submit a job to bronze queue' '
	job=$(flux python ${SUBMIT_AS} 5001 -n1 --queue=bronze hostname) &&
	flux job wait-event -f json ${job} priority | jq '.context.priority' > job.priority &&
	test $(cat job.priority) -eq 1050000 &&
	flux cancel ${job}
'

test_expect_success 'decrease priority for the bronze queue in config' '
	cat >conf.d/test.toml <<-EOT &&
	[accounting.queue-priorities]
	bronze = 0
	EOT
	flux config reload &&
	flux queue stop --all
'

test_expect_success 'submit another job to bronze queue; priority is negatively affected' '
	job=$(flux python ${SUBMIT_AS} 5001 -n1 --queue=bronze hostname) &&
	flux job wait-event -f json ${job} priority | jq '.context.priority' > job.priority &&
	test $(cat job.priority) -eq 50000 &&
	flux cancel ${job}
'

test_expect_success 'increase priority for the bronze queue in config' '
	cat >conf.d/test.toml <<-EOT &&
	[accounting.queue-priorities]
	bronze = 123
	EOT
	flux config reload &&
	flux queue stop --all
'

test_expect_success 'submit another job to bronze queue; priority is positively affected' '
	job=$(flux python ${SUBMIT_AS} 5001 -n1 --queue=bronze hostname) &&
	flux job wait-event -f json ${job} priority | jq '.context.priority' > job.priority &&
	test $(cat job.priority) -eq 1280000 &&
	flux cancel ${job}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
