#!/bin/bash

test_description='test limiting number of jobs in SCHED per-queue'

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

# Setting max-sched-jobs to 1 means that the association can have up to 1 job
# in SCHED state in the "pdebug" queue at any given time.
test_expect_success 'add a queue to DB' '
	flux account add-queue pdebug --max-sched-jobs=1
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add associations to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug \
		--max-active-jobs=10000 \
		--max-running-jobs=1000
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.pdebug]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'queue is properly configured in plugin internal data structure' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".queues.pdebug.max_sched_jobs == 1" <query.json
'

# This job will proceed to RUN immediately but take up all current resources
# of this instance, so any job submitted while this job is running will be
# placed in SCHED state.
test_expect_success 'first job proceeds to RUN immediately' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

# Since the first job is currently running, this job is placed in SCHED state
# until enough resources are freed up for this job to run.
test_expect_success 'second job gets placed in SCHED state' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority
'

# Since the association already has a job in SCHED state, this job has a
# dependency placed on it.
test_expect_success 'third submitted job has SCHED-state-related dependency' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-add
'

# When the first job gets cancelled, the second job can proceed to run because
# enough resources are freed.
test_expect_success 'second job receives alloc event' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job2} alloc
'

# When the second job proceeds to run, the job.state.run callback checks to see
# if any other jobs held due to the max_sched_jobs limit can have their
# dependency removed.
test_expect_success 'third job has max-sched-jobs dependency removed' '
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3}
'

# In this set of tests, we make sure that an association who has hit their max
# SCHED jobs per-queue limit preserves this same limit after a plugin
# reload.
test_expect_success 'submit jobs to trigger max-run-jobs per-association limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-add
'

test_expect_success 'reload plugin' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'total job counts for associations are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 3" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'job counts for association in queue are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pdebug\"].cur_run_jobs == 1" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pdebug\"].cur_sched_jobs == 1" <query.json
'

test_expect_success 'second job receives alloc event after first job goes inactive' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'third job has max-sched-jobs dependency removed' '
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3}
'

# In this set of tests, we make sure that *both* the per-association and the
# per-queue max SCHED jobs dependency are applied at the same time.
test_expect_success 'edit association to have a max_sched_jobs limit of 1' '
	flux account edit-user user1 --max-sched-jobs=1 &&
	flux account-priority-update -p ${DB} &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_sched_jobs == 1" <query.json
'

test_expect_success 'first job proceeds to RUN immediately' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

test_expect_success 'second job gets placed in SCHED state' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority
'

test_expect_success 'third submitted job has both SCHED state-related dependencies' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-add
'

# When the first job gets cancelled, the second job can proceed to run because
# enough resources are freed.
test_expect_success 'second job receives alloc event' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job2} alloc
'

# When the second job proceeds to run, the job.state.run callback checks to see
# if any other jobs held due to the max_sched_jobs limit can have their
# dependency removed.
test_expect_success 'third job has max-sched-jobs dependency removed' '
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3}
'

# In this set of tests, we make sure that with two queues, a job held in queue
# A due to a max SCHED limit is not released when a job in B transitions to RUN
# state.
test_expect_success 'add another queue and give association access to that queue' '
	flux account add-queue pbatch --max-sched-jobs=1 &&
	flux account edit-user user1 --max-sched-jobs=-1 --queues=pdebug,pbatch &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'update flux with the new queue' '
	cat >config/queues.toml <<-EOT &&
	[queues.pdebug]
	[queues.pbatch]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'association hits max-sched-jobs limit in both queues' '
	pdebug_job1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${pdebug_job1} alloc &&
	pbatch_job1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${pbatch_job1} alloc &&
	pdebug_job2=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${pdebug_job2} priority &&
	pbatch_job2=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${pbatch_job2} priority &&
	pdebug_job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${pdebug_job3} dependency-add &&
	pbatch_job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${pbatch_job3} dependency-add
'

test_expect_success 'ensure job counts for association are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 6" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pdebug\"].cur_run_jobs == 1" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pbatch\"].cur_run_jobs == 1" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pdebug\"].cur_sched_jobs == 1" <query.json &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"pbatch\"].cur_sched_jobs == 1" <query.json
'

test_expect_success 'job1 in pdebug is cancelled; job2 in pdebug can now run' '
	flux cancel ${pdebug_job1} &&
	flux job wait-event -t 5 ${pdebug_job2} alloc
'

test_expect_success 'held job in pbatch is still not released' '
	pbatch_job3_dec=$(flux job id -t dec ${pbatch_job3}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 5" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${pbatch_job3_dec}\"].deps \
			| length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${pbatch_job3_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json
'

test_expect_success 'job2 in pdebug cancelled; job2 in pbatch can run' '
	flux cancel ${pdebug_job2} &&
	flux job wait-event -t 5 ${pbatch_job2} alloc
'

test_expect_success 'dependency removed from job3 in pbatch now that job2 in pbatch runs' '
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${pbatch_job3} dependency-remove &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 4" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'cancel rest of jobs' '
	flux cancel ${pdebug_job3} ${pbatch_job1} ${pbatch_job2} ${pbatch_job3}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
