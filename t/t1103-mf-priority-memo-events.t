#!/bin/bash

test_description='test that fair-share memo events are only posted when fair-share changes'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add a queue, a bank, and an association' '
	flux account add-queue default --priority=0 &&
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user \
		--username=user1 \
		--userid=50001 \
		--bank=A \
		--queues=default
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB}
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.default]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'stop the queue so the job stays pending' '
	flux queue stop --all
'

test_expect_success 'submit a job and wait for it to receive a priority' '
	jobid=$(flux python ${SUBMIT_AS} 50001 --queue=default hostname) &&
	flux job wait-event -t 5 ${jobid} priority
'

test_expect_success 'exactly one fair-share memo event was posted' '
	flux job eventlog ${jobid} > eventlog.1 &&
	test $(grep -c fairshare eventlog.1) -eq 1 &&
	grep "fairshare=0.5" eventlog.1
'

# reprioritize once with fair-share unchanged; make sure there is still only
# one event
test_expect_success 'reprioritize with unchanged fair-share' '
	flux account-priority-update -p ${DB} &&
	flux job eventlog ${jobid} > eventlog.2 &&
	test $(grep -c fairshare eventlog.2) -eq 1 &&
	grep "fairshare=0.5" eventlog.2
'

test_expect_success 'edit fair-share and reprioritize; now there are 2 entries' '
	flux account edit-user user1 --fairshare=0.7 &&
	flux account-priority-update -p ${DB} &&
	flux job eventlog ${jobid} > eventlog.3 &&
	test $(grep -c fairshare eventlog.3) -eq 2
'

test_expect_success 'reprioritize with unchanged fair-share' '
	flux account-priority-update -p ${DB} &&
	flux job eventlog ${jobid} > eventlog.4 &&
	test $(grep -c fairshare eventlog.4) -eq 2
'

test_expect_success 'clean up job' '
	flux cancel ${jobid}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
