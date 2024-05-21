#!/bin/bash

test_description='test the age factor in multi-factor priority plugin'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'load plugin successfully without configuration' '
  	flux jobtap load ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'create a flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root bankA 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root bankB 1
'

test_expect_success 'add a user to the DB' '
	flux account -p ${DB_PATH} add-user \
		--username=user1001 \
		--userid=1001 \
		--bank=bankA &&
	flux account -p ${DB_PATH} add-user \
		--username=user1001 \
		--userid=1001 \
		--bank=bankB	
'

test_expect_success 'configure multi-factor priority plugin' '
	cat >config/test.toml <<-EOT &&
	[accounting.factor-weights]
	fairshare = 1000
	queue = 100
	age = 100
	EOT
	flux config reload
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p $(pwd)/FluxAccountingTest.db
'

# In this first set of tests, we will submit two one-node jobs with just one
# node available. While both jobs will receive a priority and be released by
# the scheduler, the second one will have to wait for the first to finish
# running before it can run. Therefore, the second job will have its time of
# release kept track of by the plugin while it waits to be run. Once time has
# passed and jobs are reprioritized, the held job's priority will increase
# since it has been waiting. The check at the end of this first set makes sure
# that the priority of the second job has increased as a result of waiting for
# the resources so that it can run.
test_expect_success 'submit two one-node jobs with just one node available' '
	job1=$(flux python ${SUBMIT_AS} 1001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 1001 -N1 sleep 60) &&
	flux job wait-event -f json ${job2} priority \
		| jq '.context.priority' > job2.priority
'

test_expect_success 'reprioritize jobs while jobs are active' '
	sleep 1.5 &&
	cat <<-EOF >fake_payload.py
	import flux

	flux.Flux().rpc("job-manager.mf_priority.reprioritize").get()
	EOF
	flux python fake_payload.py &&
	flux cancel ${job1}
'

test_expect_success 'grab new priority of job' '
	flux job info ${job2} eventlog > eventlog.out &&
	grep "priority" eventlog.out \
		| awk "NR==2" \
		| jq '.context.priority' > job2.new_priority
'

test_expect_success 'make sure the priority of the job has increased' '
	old_priority=$(cat job2.priority) &&
	new_priority=$(cat job2.new_priority) &&
	test $new_priority -gt $old_priority
'

test_expect_success 'cancel job' '
	flux cancel ${job2}
'

# In this second set of tests, a job is submitted with an urgency set to 0,
# therefore preventing it from running. When the urgency of the job is updated
# to a value greater than 0, we check that the age factor is not considered
# when re-calculating the priority of the job.
test_expect_success 'submit a job with urgency==0' '
	job=$(flux python ${SUBMIT_AS} 1001 --urgency=0 -N1 sleep 60)
'

test_expect_success 'update the urgency of the job' '
	flux job urgency ${job} 16
'

test_expect_success 'make sure priority has not increased' '
	flux job wait-event -vt 10 ${job} alloc &&
	flux job info ${job} eventlog > eventlog.out &&
	grep "priority" eventlog.out \
		| jq '.context.priority' | tail -n 1 > job.priority
	test "$(cat job.priority)" -eq 500
'

test_expect_success 'cancel job' '
	flux cancel ${job}
'

# In this set of tests, the scenario from the first set is repeated; this time,
# the second job has an urgency of 0 set to it, preventing it from running. Its
# urgency is then updated to have a value greater than 0 but cannot actually
# run since the first job is still running. Jobs are reprioritized and the job
# that previously could not run is checked to make sure that its priority has
# increased from before as a result of its age in the queue.
test_expect_success 'submit two jobs' '
	job1=$(flux python ${SUBMIT_AS} 1001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 1001 -N1 --urgency=0 sleep 60) &&
	flux job wait-event -vt 10 ${job2} priority
'

test_expect_success 'update the urgency of the second job to start considering age as a factor' '
	flux job urgency ${job2} 16
'

test_expect_success 'reprioritize jobs and cancel running job' '
	sleep 1.5 &&
	cat <<-EOF >fake_payload.py
	import flux

	flux.Flux().rpc("job-manager.mf_priority.reprioritize").get()
	EOF
	flux python fake_payload.py &&
	flux cancel ${job1}
'

test_expect_success 'priority of previously-released job increases' '
	flux job info ${job2} eventlog > eventlog.out &&
	grep "priority" eventlog.out \
		| awk "NR==2" \
		| jq '.context.priority' > job2.old_priority &&
	grep "priority" eventlog.out \
		| awk "NR==3" \
		| jq '.context.priority' > job2.new_priority
'

test_expect_success 'compare priorities of previously released job' '
	old_priority=$(cat job2.old_priority) &&
	new_priority=$(cat job2.new_priority) &&
	test $new_priority -gt $old_priority
'

test_expect_success 'cancel job' '
	flux cancel ${job2}
'

# In this set of tests, we check that updating a job to use a different bank or
# queue clears and resets the age of the job.
test_expect_success 'submit two one-node jobs with just one node available' '
	job1=$(flux python ${SUBMIT_AS} 1001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 1001 -N1 sleep 60) &&
	flux job wait-event -f json ${job2} priority \
		| jq '.context.priority' > job2.priority
'

test_expect_success 'reprioritize jobs while jobs are active (job2 will accumulate age)' '
	sleep 1.5 &&
	cat <<-EOF >fake_payload.py
	import flux

	flux.Flux().rpc("job-manager.mf_priority.reprioritize").get()
	EOF
	flux python fake_payload.py
'

test_expect_success 'change the urgency to 0 and update the bank of the released job' '
	flux job urgency ${job2} 0 &&
	flux update ${job2} bank=bankB &&
	flux job wait-event -vt 10 ${job2} priority &&
	flux job eventlog ${job2} > eventlog.out &&
	grep "attributes.system.bank=\"bankB\"" eventlog.out
'

test_expect_success 'cancel first job, update urgency of released job' '
	flux cancel ${job1} &&
	flux job urgency ${job2} 16 &&
	flux job wait-event -f json ${job2} alloc &&
	flux job info ${job2} eventlog > eventlog.out &&
	grep "priority" eventlog.out \
		| awk "NR==5" \
		| jq '.context.priority' > job2.new_priority
'

test_expect_success 'make sure priority does not factor in the age before the bank update' '
	old_priority=$(cat job2.priority) &&
	new_priority=$(cat job2.new_priority) &&
	test $new_priority -eq $old_priority
'

test_expect_success 'cancel released job' '
	flux cancel ${job2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
