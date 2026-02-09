#!/bin/bash

test_description='test configuring the weight for the urgency factor in priority plugin'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

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
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=${username} --userid=${uid} --bank=A
'

# Configuring the priority factor weights like the following will ensure that
# *only* the urgency will be used when calculating the priority for a job,
# i.e.:
#
# 	priority = (urgency_weight * (urgency - 16)) = (1000 * (urgency - 16))
test_expect_success 'configure priority factors so that urgency is the only factor' '
	flux account edit-factor --factor=fairshare --weight=0 &&
	flux account edit-factor --factor=queue --weight=0 &&
	flux account edit-factor --factor=bank --weight=0
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'stop the queue' '
	flux queue stop
'

# priority = (urgency_weight * (urgency - 16)) = (1000 * (17 - 16)) = 1000
test_expect_success 'submit a job with urgency 17' '
	job1=$(flux submit --urgency=17 sleep 60) &&
	flux job wait-event -vt 5 -f json ${job1} priority \
		| jq '.context.priority' > job1.priority &&
	grep "1000" job1.priority &&
	flux cancel ${job1}
'

# priority = (urgency_weight * (urgency - 16)) = (1000 * (15 - 16)) = -1000
# Since this priority evaluates to < 0, the plugin will return
# FLUX_JOB_PRIORITY_MIN.
test_expect_success 'submit a job with urgency 15' '
	job2=$(flux submit --urgency=15 sleep 60) &&
	flux job wait-event -vt 5 -f json ${job2} priority \
		| jq '.context.priority' > job2.priority &&
	grep "0" job2.priority &&
	flux cancel ${job2}
'

# Configuring the priority factor weights like the following will ensure that
# urgency is the *most* important factor in calculating the priority for a job,
# i.e.:
#
# priority = (100 * fairshare)
#            + (1000 * (urgency - 16))
test_expect_success 'configure priority factors so that urgency is the largest factor' '
	flux account edit-factor --factor=fairshare --weight=100 &&
	flux account-priority-update -p ${DB_PATH}
'

# priority = (fair-share weight * fair-share)
#            + (urgency weight * (urgency - 16))
# priority = (100 * 0.5) + (1000 * (18 - 16)) = 50 + 2000 = 2050
test_expect_success 'submit a job with urgency 18' '
	job3=$(flux submit --urgency=18 sleep 60) &&
	flux job wait-event -vt 5 -f json ${job3} priority \
		| jq '.context.priority' > job3.priority &&
	grep "2050" job3.priority &&
	flux cancel ${job3}
'

# priority = (fair-share weight * fair-share)
#            + (urgency weight * (urgency - 16))
# priority = (100 * 0.5) + (1000 * (17 - 16)) = 50 + 1000 = 1050
test_expect_success 'submit a job with urgency 17' '
	job4=$(flux submit --urgency=17 sleep 60) &&
	flux job wait-event -vt 5 -f json ${job4} priority \
		| jq '.context.priority' > job4.priority &&
	grep "1050" job4.priority &&
	flux cancel ${job4}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
