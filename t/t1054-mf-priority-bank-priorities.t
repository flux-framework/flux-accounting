#!/bin/bash

test_description='test priority plugin bank priority factor'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
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

# Configure the banks in flux-accounting to have varying priorities. These
# priorities will affect the overall priority for a job.
test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root --priority=1 A 1 &&
	flux account add-bank --parent-bank=root --priority=2 B 1 &&
	flux account add-bank --parent-bank=root --priority=3.5 C 1
'

test_expect_success 'add three different associations' '
	flux account add-user --username=user1 --userid=50001 --bank=A &&
	flux account add-user --username=user1 --userid=50001 --bank=B &&
	flux account add-user --username=user1 --userid=50001 --bank=C
'

test_expect_success 'send the user and queue information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

# Configuring the priority factor weights like the following will ensure that
# *only* the "bank" factor will be used when calculating the priority for a
# job, i.e.:
#
# 		priority = (bank_priority * bank_weight) = (bank_priority * 100)
test_expect_success 'make "bank" the only factor in priority calculation' '
	flux account edit-factor --factor=fairshare --weight=0 &&
	flux account edit-factor --factor=queue --weight=0 &&
	flux account edit-factor --factor=bank --weight=100 &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'stop the queue' '
	flux queue stop
'

# priority = (bank_priority * bank_weight) = (1 * 100) = 100
test_expect_success 'submit a job to bank A' '
	job1=$(flux python ${SUBMIT_AS} 50001 sleep 60) &&
	flux job wait-event -vt 5 -f json ${job1} priority \
		| jq '.context.priority' > job1.priority &&
	grep "100" job1.priority &&
	flux cancel ${job1}
'

# priority = (bank_priority * bank_weight) = (2 * 100) = 200
test_expect_success 'submit a job to bank B' '
	job2=$(flux python ${SUBMIT_AS} 50001 -S bank=B sleep 60) &&
	flux job wait-event -vt 5 -f json ${job2} priority \
		| jq '.context.priority' > job2.priority &&
	grep "200" job2.priority &&
	flux cancel ${job2}
'

# priority = (bank_priority * bank_weight) = (3.5 * 100) = 350
test_expect_success 'submit a job to bank C' '
	job3=$(flux python ${SUBMIT_AS} 50001 -S bank=C sleep 60) &&
	flux job wait-event -vt 5 -f json ${job3} priority \
		| jq '.context.priority' > job3.priority &&
	grep "350" job3.priority
'

# If a pending job is updated to run under a different bank, there is chance
# its priority could be affected. In this case, a job is updated to run under
# bank B instead of bank C, and thus its priority decreases from 350 to 200.
test_expect_success 'update the bank of the pending job and check priority' '
	flux update ${job3} bank=B &&
	flux job wait-event -vt 3 --match-context=attributes.system.bank=B \
		${job3} jobspec-update &&
	flux job info ${job3} eventlog > job3.updated_priority &&
	grep "\"name\":\"priority\",\"context\":{\"priority\":200}" \
		job3.updated_priority &&
	flux cancel ${job3}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
