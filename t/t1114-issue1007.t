#!/bin/bash

test_description='test pending job bank is preserved across priority plugin reload'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'add banks and association to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-user \
		--username=user1 --userid=50001 --bank=A &&
	flux account add-user \
		--username=user1 --userid=50001 --bank=B
'

test_expect_success 'change default bank before job submission' '
	flux account edit-user user1 --default-bank=B &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'stop scheduler so job remains pending' '
	flux queue stop
'

test_expect_success 'submit pending job under non-default bank' '
	jobid=$(flux python ${SUBMIT_AS} 50001 \
		--setattr=system.bank=A hostname) &&
	flux job wait-event -t 5 ${jobid} priority &&
	flux job info ${jobid} jobspec > jobspec-before-reload.json &&
	jq -e ".attributes.system.bank == \"A\"" \
		<jobspec-before-reload.json
'

test_expect_success 'submit pending job under default bank' '
	jobid2=$(flux python ${SUBMIT_AS} 50001 hostname) &&
	flux job wait-event -t 5 ${jobid2} priority &&
	flux job info ${jobid2} jobspec | jq -e ".attributes.system.bank == \"B\""
'

# change the default bank to a third bank so that an unconditional
# overwrite with the default bank would be caught for both pending jobs
test_expect_success 'change default bank while jobs are pending' '
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-user --username=user1 --userid=50001 --bank=C &&
	flux account edit-user user1 --default-bank=C &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'reload priority plugin without accounting data' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'send accounting data to reloaded priority plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'reload preserves bank selected at submission' '
	flux job info ${jobid} jobspec > jobspec-after-reload.json &&
	test_debug "jq -S . <jobspec-after-reload.json" &&
	jq -e ".attributes.system.bank == \"A\"" \
		<jobspec-after-reload.json
'

test_expect_success 'reload preserves default bank set at submission' '
	flux job info ${jobid2} jobspec | jq -e ".attributes.system.bank == \"B\""
'

test_expect_success 'cancel pending jobs' '
	flux cancel ${jobid} ${jobid2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
