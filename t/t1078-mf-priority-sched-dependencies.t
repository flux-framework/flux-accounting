#!/bin/bash

test_description='test limiting number of jobs in SCHED per-association'

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

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

# Setting max-sched-jobs to 1 means that the association can have up to 1 job
# in SCHED state at any given time.
test_expect_success 'add associations' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--max-sched-jobs=1
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'association is in priority plugin data structure' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	cat query.json | jq &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_sched_jobs == 1" <query.json
'

# This job will proceed to RUN immediately but take up all current resources
# of this instance, so any job submitted while this job is running will be
# placed in SCHED state.
test_expect_success 'first job proceeds to RUN immediately' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

# Since the first job is currently running, this job is placed in SCHED state
# until enough resources are freed up for this job to run.
test_expect_success 'second job gets placed in SCHED state' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job2} priority
'

# Since the association already has a job in SCHED state, this job has a
# dependency placed on it.
test_expect_success 'third submitted job has SCHED-state-related dependency' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
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
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3}
'

# In this set of tests, we make sure that an association who has hit their max
# SCHED jobs per-association limit preserves this same limit after a plugin
# reload.
test_expect_success 'submit 2 jobs to trigger max-run-jobs per-association limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-add
'

test_expect_success 'reload plugin' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'look at job counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	cat query.json | jq &&
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

test_expect_success 'check flux jobs' '
	flux jobs -A
'

test_expect_success 'second job receives alloc event' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'third job has max-sched-jobs dependency removed' '
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
