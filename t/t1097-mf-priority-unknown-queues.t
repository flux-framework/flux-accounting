#!/bin/bash

test_description='test accepting jobs to queues unknown to flux-accounting'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

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

test_expect_success 'add a queue to DB' '
	flux account add-queue pdebug
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug
'

test_expect_success 'load and initialize priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

# Add a queue that flux-accounting does not know about
test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.pdebug]
	[queues.foo]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'pdebug queue is listed in internal data structure' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	grep "pdebug" query.json
'

test_expect_success 'association can submit job to pdebug queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

test_expect_success 'association can also submit job to foo queue' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=foo sleep inf) &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job' '
	flux cancel ${job1} &&
	flux cancel ${job2}
'

test_expect_success 'enable deny_unknown_queues config option' '
	flux account edit-config deny_unknown_queues=true
'

test_expect_success 'reload plugin with deny_unknown_queues enabled' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq
'

test_expect_success 'job to known queue (pdebug) still works' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job3} alloc &&
	flux cancel ${job3}
'

test_expect_success 'job to unknown queue (foo) now rejected' '
	test_must_fail flux python ${SUBMIT_AS} 50001 -N1 --queue=foo sleep inf 2>err &&
	grep "queue.*foo.*unknown.*flux-accounting.*deny-unknown-queues" err
'

test_expect_success 'disable deny_unknown_queues and reload plugin' '
	flux account edit-config deny_unknown_queues=false &&
	flux jobtap remove mf_priority.so &&
	flux jobtap load \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)"
'

test_expect_success 'job to unknown queue (foo) accepted again' '
	job4=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=foo sleep inf) &&
	flux job wait-event -t 5 ${job4} alloc &&
	flux cancel ${job4}
'

test_expect_success 'enable deny_unknown_queues via priority-update' '
	flux account edit-config deny_unknown_queues=true &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'job to known queue (pdebug) still works after priority-update' '
	job5=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job5} alloc &&
	flux cancel ${job5}
'

test_expect_success 'job to unknown queue (foo) rejected after priority-update' '
	test_must_fail flux python ${SUBMIT_AS} 50001 -N1 --queue=foo sleep inf 2>err2 &&
	grep "queue.*foo.*unknown.*flux-accounting.*deny-unknown-queues" err2
'

test_expect_success 'disable deny_unknown_queues via priority-update' '
	flux account edit-config deny_unknown_queues=false &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'job to unknown queue (foo) accepted after priority-update disable' '
	job6=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=foo sleep inf) &&
	flux job wait-event -t 5 ${job6} alloc &&
	flux cancel ${job6}
'

test_expect_success 'reject invalid value for deny_unknown_queues (yes)' '
	test_must_fail flux account edit-config deny_unknown_queues=yes 2>invalid_err1 &&
	grep "must be.*true.*false" invalid_err1
'

test_expect_success 'reject invalid value for deny_unknown_queues (1)' '
	test_must_fail flux account edit-config deny_unknown_queues=1 2>invalid_err2 &&
	grep "must be.*true.*false" invalid_err2
'

test_expect_success 'reject invalid value for deny_unknown_queues (enabled)' '
	test_must_fail flux account edit-config deny_unknown_queues=enabled 2>invalid_err3 &&
	grep "must be.*true.*false" invalid_err3
'

test_expect_success 'verify deny_unknown_queues still set to false after invalid attempts' '
	flux account view-config deny_unknown_queues > view_output &&
	grep "false" view_output
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
