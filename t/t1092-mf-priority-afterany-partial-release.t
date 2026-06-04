#!/bin/bash

test_description='test partial release of held jobs in priority plugin'

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
		--max-running-jobs=9999 \
		--max-sched-jobs=1
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
		 .banks[0].cur_active_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_sched_jobs == 1" <query.json
'

test_expect_success 'submit enough jobs to take up max_sched_jobs limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority
'

test_expect_success 'jobs are held with both afterany dependency and max-sched-jobs limit' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N4 --dependency=afterany:${job1} --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="after-finish=${job1}" \
		${job3} dependency-add &&
	job4=$(flux python ${SUBMIT_AS} 50001 -N4 --dependency=afterany:${job1} --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job4} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="after-finish=${job1}" \
		${job4} dependency-add
'

test_expect_success 'association has 1 job in RUN, 1 in SCHED, and 2 in DEPEND'  '
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
		 .banks[0].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json
'

test_expect_success 'held jobs have correct accounting dependencies' '
	job3_dec=$(flux job id -t dec ${job3}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job3_dec}\"].deps[0] \
			== \"max-sched-jobs-user-limit\"" <query.json &&
	job4_dec=$(flux job id -t dec ${job4}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job4_dec}\"].deps[0] \
			== \"max-sched-jobs-user-limit\"" <query.json
'

test_expect_success 'cancel job2 in SCHED; job3 has its accounting dependency removed' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job3} dependency-remove
'

test_expect_success 'job4 still has its max-sched-jobs dependency' '
	job4_dec=$(flux job id -t dec ${job4}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job4_dec}\"].deps[0] \
			== \"max-sched-jobs-user-limit\"" <query.json
'

test_expect_success 'cancel job1; job3 can now proceed to RUN' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job3} alloc
'

test_expect_success 'association job counts are accurate' '
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
		 .banks[0].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job3} ${job4} &&
	flux job wait-event -t 5 ${job3} clean &&
	flux job wait-event -t 5 ${job4} clean
'

test_expect_success 'association job counts are accurate' '
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
		 .banks[0].cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

# This set of tests repeat the same scenario as above, but with the per-queue
# max-sched-jobs limit.
test_expect_success 'update queue max-sched-jobs limit to 1' '
	flux account edit-user user1 --max-sched-jobs=-1 &&
	flux account edit-queue pdebug --max-sched-jobs=1 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'submit enough jobs to take up max_sched_jobs limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job2} priority
'

test_expect_success 'jobs are held with both afterany dependency and max-sched-jobs limit' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N4 --dependency=afterany:${job1} --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="after-finish=${job1}" \
		${job3} dependency-add &&
	job4=$(flux python ${SUBMIT_AS} 50001 -N4 --dependency=afterany:${job1} --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job4} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="after-finish=${job1}" \
		${job4} dependency-add
'

test_expect_success 'association has 1 job in RUN, 1 in SCHED, and 2 in DEPEND'  '
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
		 .banks[0].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_sched_jobs == 1" <query.json

'

test_expect_success 'held jobs have correct accounting dependencies' '
	job3_dec=$(flux job id -t dec ${job3}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job3_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json &&
	job4_dec=$(flux job id -t dec ${job4}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job4_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json
'

test_expect_success 'cancel job2 in SCHED; job3 has its accounting dependency removed' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${job3} dependency-remove
'

test_expect_success 'job4 still has its max-sched-jobs dependency' '
	job4_dec=$(flux job id -t dec ${job4}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job4_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json
'

test_expect_success 'cancel job1; job3 can now proceed to RUN' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job3} alloc
'

test_expect_success 'association job counts are accurate' '
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
		 .banks[0].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_sched_jobs == 1" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job3} ${job4} &&
	flux job wait-event -t 5 ${job3} clean &&
	flux job wait-event -t 5 ${job4} clean
'

test_expect_success 'association job counts are accurate' '
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
		 .banks[0].cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_sched_jobs == 0" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
