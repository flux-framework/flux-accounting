#!/bin/bash

test_description='test limiting total scheduled resources per queue'

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

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add queues to DB' '
	flux account add-queue ptotal --max-nodes=4 --max-cores=4 &&
	flux account add-queue pfill
'

test_expect_success 'add associations to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=ptotal,pfill \
		--max-active-jobs=10000 \
		--max-running-jobs=1000 &&
	flux account add-user \
		--username=user2 \
		--bank=B \
		--userid=50002 \
		--queues=ptotal \
		--max-active-jobs=10000 \
		--max-running-jobs=1000
'

test_expect_success 'load and initialize priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.ptotal]
	[queues.pfill]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'queue total limits are configured in plugin' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.ptotal.max_nodes == 4" <query.json &&
	jq -e ".queues.ptotal.max_cores == 4" <query.json
'

test_expect_success 'user1 job fills ptotal while waiting in SCHED' '
	filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${filler} alloc &&
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 ${job1} priority
'

test_expect_success 'user2 job is held on queue-total node and core limits' '
	job2=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${job2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${job2} dependency-add
'

test_expect_success 'SCHED to RUN does not release queue-total dependencies' '
	flux cancel ${filler} &&
	flux job wait-event -t 5 ${job1} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] |
		   select(.userid == 50002) |
		   .banks[0].held_jobs |
		   length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"$(flux job id -t dec ${job2})\"].deps[0] \
			== \"max-nodes-total-queue-limit\"" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"$(flux job id -t dec ${job2})\"].deps[1] \
			== \"max-cores-total-queue-limit\"" <query.json
'

test_expect_success 'inactive event releases held job across associations' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${job2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${job2} dependency-remove &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'clean up jobs' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean &&
	flux job wait-event -t 5 ${job1} clean &&
	flux job wait-event -t 5 ${filler} clean
'

# This set of tests ensures that the global queue-total SCHED/RUN node and
# core counts are correctly counted after a plugin restart.
test_expect_success 'submit enough jobs to fill queue-total headroom' '
	reload_filler=$(flux python ${SUBMIT_AS} 50001 \
		-N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${reload_filler} alloc &&
	reload_job1=$(flux python ${SUBMIT_AS} 50001 \
		-N4 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 ${reload_job1} priority
'

test_expect_success 'user1 has 4 nodes and 4 cores in ptotal SCHED state' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.ptotal.cur_sched_nodes == 4" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.ptotal.cur_sched_cores == 4" <query.json
'

test_expect_success 'user2 job is held on queue-total limits before reload' '
	reload_job2=$(flux python ${SUBMIT_AS} 50002 \
		-N1 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${reload_job2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${reload_job2} dependency-add
'

test_expect_success 'reload plugin' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'user1 ptotal SCHED resource counts survive reload' '
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
		 .banks[0].queue_usage.ptotal.cur_sched_nodes == 4" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.ptotal.cur_sched_cores == 4" <query.json
'

test_expect_success 'queue-total dependencies are preserved after reload' '
	reload_job2_dec=$(flux job id -t dec ${reload_job2}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"${reload_job2_dec}\"].deps | length == 2" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"${reload_job2_dec}\"].deps |
		 index(\"max-nodes-total-queue-limit\")" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"${reload_job2_dec}\"].deps |
		 index(\"max-cores-total-queue-limit\")" <query.json
'

test_expect_success 'clean up reload jobs' '
	flux cancel ${reload_job1} ${reload_job2} ${reload_filler} &&
	flux job wait-event -t 5 ${reload_job1} clean &&
	flux job wait-event -t 5 ${reload_job2} clean &&
	flux job wait-event -t 5 ${reload_filler} clean
'

# This scenario checks that queue-total limits are re-evaluated before a held
# job is released. The job is initially held only by max-sched-jobs, then
# another association fills the target queue's total resource headroom. When
# max-sched-jobs clears, the job should gain queue-total dependencies instead
# of moving to SCHED and exceeding the queue-wide limit.
test_expect_success 'configure user1 to hold on max-sched-jobs' '
	flux account edit-user user1 --max-sched-jobs=1 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'user1 job is held without queue-total dependencies' '
	stale_filler=$(flux python ${SUBMIT_AS} 50001 \
		-N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${stale_filler} alloc &&
	stale_blocker=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${stale_blocker} priority &&
	stale_held=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${stale_held} dependency-add &&
	stale_held_dec=$(flux job id -t dec ${stale_held}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${stale_held_dec}\"].deps |
		 index(\"max-nodes-total-queue-limit\") | not" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${stale_held_dec}\"].deps |
		 index(\"max-cores-total-queue-limit\") | not" <query.json
'

test_expect_success 'another association fills queue-total headroom' '
	stale_total=$(flux python ${SUBMIT_AS} 50002 \
		-N4 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 ${stale_total} priority
'

test_expect_success 'release sweep rechecks queue-total limits' '
	flux cancel ${stale_blocker} &&
	flux job wait-event -t 5 ${stale_blocker} clean &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${stale_held} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${stale_held} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${stale_held} dependency-remove &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${stale_held_dec}\"].deps |
		 index(\"max-nodes-total-queue-limit\")" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${stale_held_dec}\"].deps |
		 index(\"max-cores-total-queue-limit\")" <query.json
'

test_expect_success 'clean up stale dependency jobs' '
	flux cancel ${stale_held} ${stale_total} ${stale_filler} &&
	flux job wait-event -t 5 ${stale_held} clean &&
	flux job wait-event -t 5 ${stale_total} clean &&
	flux job wait-event -t 5 ${stale_filler} clean
'

# This scenario checks that one queue-total dependency is not removed before
# the other total-resource dimension has been rechecked. The held job first
# gets only a node-total dependency. The core limit is then tightened while the
# job is held, and the node limit is loosened. The release sweep should add the
# core-total dependency before removing the now-stale node-total dependency.
test_expect_success 'configure asymmetric queue-total limits' '
	flux account edit-user user1 --max-sched-jobs=-1 &&
	flux account edit-queue ptotal --max-nodes=4 --max-cores=8 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'job is held only on queue-total node limit' '
	asym_filler=$(flux python ${SUBMIT_AS} 50001 \
		-N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${asym_filler} alloc &&
	asym_total=$(flux python ${SUBMIT_AS} 50001 \
		-N4 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 ${asym_total} priority &&
	asym_held=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --queue=ptotal sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${asym_held} dependency-add &&
	asym_held_dec=$(flux job id -t dec ${asym_held}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${asym_held_dec}\"].deps |
		 index(\"max-nodes-total-queue-limit\")" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${asym_held_dec}\"].deps |
		 index(\"max-cores-total-queue-limit\") | not" <query.json
'

test_expect_success 'release sweep adds core dep before node dep removal' '
	flux account edit-queue ptotal --max-nodes=5 --max-cores=4 &&
	flux account-priority-update -p ${DB} &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${asym_held} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${asym_held_dec}\"].deps |
		 index(\"max-nodes-total-queue-limit\")" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${asym_held_dec}\"].deps |
		 index(\"max-cores-total-queue-limit\")" <query.json
'

test_expect_success 'asymmetric queue-total job releases when limits fit' '
	flux account edit-queue ptotal --max-cores=8 &&
	flux account-priority-update -p ${DB} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-total-queue-limit" \
		${asym_held} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-total-queue-limit" \
		${asym_held} dependency-remove
'

test_expect_success 'clean up asymmetric queue-total jobs' '
	flux cancel ${asym_held} ${asym_total} ${asym_filler} &&
	flux job wait-event -t 5 ${asym_held} clean &&
	flux job wait-event -t 5 ${asym_total} clean &&
	flux job wait-event -t 5 ${asym_filler} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
