#!/bin/bash

test_description='test partial release of held jobs in a queue in priority plugin'

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

test_expect_success 'add an association to the DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug \
		--max-active-jobs=10000 \
		--max-running-jobs=9999
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.pdebug]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'load and initialize priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

# This set of tests makes sure that if an association has held jobs due to
# max_sched_jobs, their counters for current SCHED jobs are accurate as jobs
# are released
test_expect_success 'association job counts are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 0" <query.json
'

test_expect_success 'edit max_sched_jobs of the queue to 2' '
	flux account edit-queue pdebug --max-sched-jobs=2 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'submit enough jobs to take up max_sched_jobs limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job3} priority
'

test_expect_success 'association has 1 job in RUN, 2 jobs in SCHED' '
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
		 .banks[0].cur_sched_jobs == 2" <query.json
'

test_expect_success 'jobs are held with max-sched-jobs-queue-limit' '
	job4=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job4} dependency-add &&
	job5=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job5} dependency-add &&
	job6=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job6} dependency-add
'

test_expect_success 'association has 1 job in RUN, 2 jobs in SCHED, 3 jobs in DEPEND' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 6" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 3" <query.json
'

# If the two jobs in SCHED state are cancelled, then job4 and job5 (the first
# two held jobs due to the max_sched_jobs limit) can be released and held in
# SCHED, but job6 will still be held in DEPEND
test_expect_success 'cancel job2 and job3; job4 and job5 proceed to SCHED' '
	flux cancel ${job2} ${job3} &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job4} dependency-remove && 
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job5} dependency-remove
'

test_expect_success 'job6 still held in DEPEND' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	job6_dec=$(flux job id -t dec ${job6}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job6_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json
'

test_expect_success 'association job counts are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 4" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json
'

test_expect_success 'if another job in SCHED state is cancelled, job6 can proceed to SCHED' '
	flux cancel ${job4} &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job6} dependency-remove
'

test_expect_success 'association has 1 job in RUN, 2 jobs in SCHED' '
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
		 .banks[0].cur_sched_jobs == 2" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} ${job5} ${job6} &&
	flux job wait-event -t 5 ${job1} clean &&
	flux job wait-event -t 5 ${job5} clean &&
	flux job wait-event -t 5 ${job6} clean
'

test_expect_success 'association has 0 jobs in RUN, 0 jobs in SCHED' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 0" <query.json
'

# This next set of tests replicates the same scenario but with the
# per-queue max-running-jobs limit.
test_expect_success 'set queue max-running-jobs limit' '
	flux account edit-queue pdebug --max-sched-jobs=-1 --max-running-jobs=1 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'new limits for association are accurate' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.pdebug.max_running_jobs == 1" <query.json
'

test_expect_success 'submit 3 jobs; 1 will proceed to RUN, 2 will be held in DEPEND' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-add
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${job3} dependency-add
'

test_expect_success 'association has 1 job in RUN, 2 jobs in DEPEND' '
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
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json &&
	job2_dec=$(flux job id -t dec ${job2}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job2_dec}\"].deps[0] \
			== \"max-run-jobs-queue\"" <query.json &&
	job3_dec=$(flux job id -t dec ${job3}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job3_dec}\"].deps[0] \
			== \"max-run-jobs-queue\"" <query.json
'

test_expect_success 'job2 can proceed to RUN after job1 is cancelled' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-remove
'

test_expect_success 'association has 1 job in RUN, 1 job in DEPEND' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job3_dec}\"].deps[0] \
			== \"max-run-jobs-queue\"" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job2} ${job3} &&
	flux job wait-event -t 5 ${job2} clean &&
	flux job wait-event -t 5 ${job3} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
