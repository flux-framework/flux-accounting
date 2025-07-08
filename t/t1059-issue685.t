#!/bin/bash

test_description='test ensuring fair-share values stay accurate in jobs output'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

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
	flux account add-bank --parent-bank=root A 1 --priority=100
'

test_expect_success 'add a queue to the DB' '
	flux account add-queue bronze --priority=1
'

test_expect_success 'add an association' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=${username} --userid=${uid} --bank=A --queues=bronze
'

test_expect_success 'configure flux with those queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	EOT
	flux config reload
'

test_expect_success 'configure priority plugin with bank factor weight' '
	flux account edit-factor --factor=bank --weight=1000
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit job 1' '
	job1=$(flux submit -S bank=A --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 ${job1} priority &&
	flux cancel ${job1}
'

test_expect_success 'update job usage and fairshare, resend info to plugin' '
	flux account-fetch-job-records -p ${DB_PATH} &&
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH} &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit job 2' '
	job2=$(flux submit -S bank=A --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 ${job2} priority
'

test_expect_success 'call flux account jobs; make sure fair-share values are accurate' '
	flux account jobs ${username} \
		-o "{JOBID:<8} | {FAIRSHARE:<10} | {PRIORITY:<10}" \
		> different_fairshare.out &&
	grep "JOBID    | FAIRSHARE  | PRIORITY " different_fairshare.out &&
	grep "1.0        | 210000" different_fairshare.out | grep ${job2} &&
	grep "0.5        | 160000" different_fairshare.out | grep ${job1}
'

test_expect_success 'cancel second job' '
	flux cancel ${job2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
