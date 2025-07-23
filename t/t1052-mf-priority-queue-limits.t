#!/bin/bash

test_description='test priority plugin max-running-jobs per-queue limits'

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

test_expect_success 'add queues with different running jobs limits' '
	flux account add-queue bronze --max-running-jobs=3 &&
	flux account add-queue silver --max-running-jobs=2 &&
	flux account add-queue gold --max-running-jobs=1
'

test_expect_success 'add a user' '
	flux account add-user \
		--username=user1 \
		--userid=5001 \
		--bank=bankA \
		--queues="bronze,silver,gold" \
		--max-running-jobs=100 \
		--max-active-jobs=100
'

test_expect_success 'send the user and queue information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'configure flux with those queues' '
	cat >conf.d/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload &&
	flux queue start --all
'

# In this set of tests, an association belongs to all three available queues,
# and each queue has a different limit on the number of running jobs available
# per-association. The association will submit the max number of running jobs
# to the silver queue (2 jobs). A dependency specific to the number of running
# jobs per-queue is added to the third submitted job in the silver queue, but
# jobs submitted to other queues will still receive an alloc event.
#
# Once one of the currently running jobs in the silver queue completes and is
# cleaned up, the job with a dependency added to it will have its dependency
# removed and will receive its alloc event.
test_expect_success 'submit max number of jobs to silver queue' '
	job1=$(flux python ${SUBMIT_AS} 5001 --queue=silver sleep 60) &&
	job2=$(flux python ${SUBMIT_AS} 5001 --queue=silver sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc &&
	flux job wait-event -vt 5 ${job2} alloc
'

test_expect_success 'running jobs count for the queues are incremented once jobs start' '
	flux jobtap query mf_priority.so > silver.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].queue_usage[\"silver\"].cur_run_jobs == 2" <silver.json
'

test_expect_success 'a third job to the silver queue results in a dependency-add' '
	job3=$(flux python ${SUBMIT_AS} 5001 --queue=silver sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-run-jobs-queue" \
		${job3} dependency-add
'

test_expect_success 'association can submit other jobs to other queues in the meantime' '
	job4=$(flux python ${SUBMIT_AS} 5001 --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 ${job4} alloc
'

test_expect_success 'check overall jobs counts for user' '
	flux jobtap query mf_priority.so > user1.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_run_jobs == 3" <user1.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_active_jobs == 4" <user1.json
'

test_expect_success 'cancel currently running job in silver queue' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job1} clean
'

test_expect_success 'wait for alloc on held job and then cancel second and third jobs' '
	flux job wait-event -vt 5 ${job3} alloc &&
	flux cancel ${job2} &&
	flux cancel ${job3} &&
	flux job wait-event -vt 5 ${job2} clean &&
	flux job wait-event -vt 5 ${job3} clean
'

test_expect_success 'cancel job in bronze queue' '
	flux cancel ${job4} &&
	flux job wait-event -vt 5 ${job4} clean
'

test_expect_success 'running jobs count for the queues are decremented once jobs exit' '
	flux jobtap query mf_priority.so > query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].queue_usage[\"silver\"].cur_run_jobs == 0" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_run_jobs == 0" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_active_jobs == 0" <query.json
'

# In this set of tests, the association will have a max running jobs limit
# that is less than the number of jobs they can run in a given queue. In this
# case, the association will have a more general running jobs limit dependency
# added to their job instead of the queue-specific dependency.
test_expect_success 'edit the max-running-jobs limit of the association' '
	flux account edit-user user1 --max-running-jobs=2 &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit max running jobs to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 5001 --queue=bronze sleep 60) &&
	job2=$(flux python ${SUBMIT_AS} 5001 --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc &&
	flux job wait-event -vt 5 ${job2} alloc
'

test_expect_success 'a third submitted job (regardless of queue) results in dependency-add' '
	job3=$(flux python ${SUBMIT_AS} 5001 --queue=silver sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job3} dependency-add
'

test_expect_success 'check active/running jobs counts' '
	flux jobtap query mf_priority.so > user1.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].held_jobs | length == 1" <user1.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_run_jobs == 2" <user1.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 5001) | \
		.banks[0].cur_active_jobs == 3" <user1.json
'

test_expect_success 'cancel currently running job; held job gets alloc event' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job1} clean &&
	flux job wait-event -vt 5 ${job3} alloc &&
	flux job wait-event -vt 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel running jobs' '
	flux cancel ${job2} &&
	flux cancel ${job3}
'

# In this set of tests, an association hits both their max running jobs limit
# *as well as* the max running jobs limit for a specific queue. In this case,
# BOTH dependencies are added to the job. Once a currently running job in this
# queue completes, the dependencies are checked one at a time to make sure that
# both conditions are satisfied before releasing the job to be scheduled to be
# run.
test_expect_success 'add a user' '
	flux account add-user \
		--username=user2 \
		--userid=5002 \
		--bank=bankA \
		--queues="gold" \
		--max-running-jobs=1 &&
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit enough jobs to take up both limits' '
	job1=$(flux python ${SUBMIT_AS} 5002 --queue=gold sleep 60) &&
	flux job wait-event -vt 10 ${job1} priority
'

test_expect_success 'ensure both dependencies get added to job' '
	job2=$(flux python ${SUBMIT_AS} 5002 --queue=gold sleep 60) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-running-jobs-user-limit" \
		${job2} dependency-add &&
	flux job wait-event -vt 10 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5002) | .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'once enough resources have been freed up, job can transition to run' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job2} dependency-remove &&
	flux job wait-event -vt 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-remove &&
	flux job wait-event -vt 10 ${job2} alloc
'

test_expect_success 'cancel running job' '
	flux cancel ${job2}
'

test_expect_success 'make sure association has no held jobs in their Association object' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
