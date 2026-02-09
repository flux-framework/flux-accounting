#!/bin/bash

test_description='test priority plugin validating jobs with no configured queues'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

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

# In this set of tests, no queues are configured for flux-accounting, which
# means the priority plugin should not do any sort of queue validation or limit
# checks for the association when submitting their jobs.
test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'make sure association has no current usage under queue' '
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queues | length == 0" <query.json
'

test_expect_success 'configure flux with queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.batch]
	[queues.debug]
	[policy.jobspec.defaults.system]
	queue = "batch"
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'job submitted under default queue gets alloc event' '
	job1=$(flux python ${SUBMIT_AS} 50001 -n1 sleep 60) &&
	flux job wait-event -vt 3 ${job1} alloc
'

test_expect_success 'second job submitted under default queue also gets alloc event' '
	job2=$(flux python ${SUBMIT_AS} 50001 -n1 sleep 60) &&
	flux job wait-event -vt 3 ${job2} alloc
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2}
'

test_expect_success 'make sure association has no current usage under queue' '
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queues | length == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
