#!/bin/bash

test_description='test global held-job release sweep in priority plugin'

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
	flux account add-queue psweep \
		--max-sched-nodes-per-assoc=1 \
		--max-sched-cores-per-assoc=1 &&
	flux account add-queue pfill
'

test_expect_success 'add associations to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=psweep,pfill \
		--max-active-jobs=10000 \
		--max-running-jobs=1000 &&
	flux account edit-user user1 --fairshare=0.5 &&
	flux account add-user \
		--username=user2 \
		--bank=B \
		--userid=50002 \
		--queues=psweep \
		--max-active-jobs=10000 \
		--max-running-jobs=1000 &&
	flux account edit-user user2 --fairshare=0.5
'

test_expect_success 'load and initialize priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.psweep]
	[queues.pfill]
	EOT
	flux config reload &&
	flux queue start --all
'

# We use a separate helper instead of utilizing flux-accounting's
# "priority-update" script so that jobs submitted later in this test are not
# reprioritized before the test executes.
test_expect_success 'create psweep queue update helper' '
	cat >psweep_queue_update.py <<-EOF
	import flux
	import json
	import sys

	max_sched_resources = int(sys.argv[1])
	bulk_queue_data = {
		"data": [
			{
				"queue": "psweep",
				"min_nodes_per_job": 0,
				"max_nodes_per_job": 2147483647,
				"max_time_per_job": 2147483647,
				"priority": 0,
				"max_running_jobs": 2147483647,
				"max_nodes_per_assoc": 2147483647,
				"max_sched_jobs": 2147483647,
				"max_sched_nodes_per_assoc": max_sched_resources,
				"max_sched_cores_per_assoc": max_sched_resources,
			},
		],
	}
	flux.Flux().rpc(
		"job-manager.mf_priority.rec_q_update",
		json.dumps(bulk_queue_data),
	).get()
	EOF
'

# This scenario prepares for limits that require a cross-association release
# sweep. Released jobs from user1 must not consume speculative headroom for
# user2 in the same pass when held jobs are checked.
test_expect_success 'associations fill psweep SCHED resource headroom' '
	sweep_filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${sweep_filler} alloc &&
	sweep_trigger=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=psweep sleep inf) &&
	flux job wait-event -t 5 ${sweep_trigger} priority &&
	sweep_b_sched=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=psweep sleep inf) &&
	flux job wait-event -t 5 ${sweep_b_sched} priority
'

test_expect_success 'both associations have held jobs in the same queue' '
	sweep_a_held1=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --dependency=afterany:${sweep_filler} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_a_held1} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_a_held1} dependency-add &&
	sweep_a_held2=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --dependency=afterany:${sweep_filler} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_a_held2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_a_held2} dependency-add &&
	sweep_b_held1=$(flux python ${SUBMIT_AS} 50002 \
		-N1 --dependency=afterany:${sweep_b_sched} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_b_held1} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_b_held1} dependency-add &&
	sweep_b_held2=$(flux python ${SUBMIT_AS} 50002 \
		-N1 --dependency=afterany:${sweep_b_sched} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_b_held2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_b_held2} dependency-add
'

test_expect_success 'raise psweep queue limit without reprioritizing' '
	flux python psweep_queue_update.py 3 &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.psweep.max_sched_nodes_per_assoc == 3" <query.json &&
	jq -e ".queues.psweep.max_sched_cores_per_assoc == 3" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 2" <query.json
'

test_expect_success 'inactive event releases held jobs from both associations' '
	flux cancel ${sweep_trigger} &&
	flux job wait-event -t 5 ${sweep_trigger} clean &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_a_held1} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_a_held1} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_a_held2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_a_held2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_b_held1} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_b_held1} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${sweep_b_held2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${sweep_b_held2} dependency-remove
'

test_expect_success 'cancel all-association sweep jobs' '
	flux cancel \
		${sweep_a_held1} \
		${sweep_a_held2} \
		${sweep_b_held1} \
		${sweep_b_held2} &&
	flux job wait-event -t 5 ${sweep_a_held1} clean &&
	flux job wait-event -t 5 ${sweep_a_held2} clean &&
	flux job wait-event -t 5 ${sweep_b_held1} clean &&
	flux job wait-event -t 5 ${sweep_b_held2} clean &&
	flux cancel ${sweep_filler} ${sweep_b_sched} &&
	flux job wait-event -t 5 ${sweep_filler} clean &&
	flux job wait-event -t 5 ${sweep_b_sched} clean
'

test_expect_success 'reset psweep queue limit for reprioritize sweep' '
	flux python psweep_queue_update.py 1 &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.psweep.max_sched_nodes_per_assoc == 1" <query.json &&
	jq -e ".queues.psweep.max_sched_cores_per_assoc == 1" <query.json
'

test_expect_success 'associations fill psweep SCHED headroom for reprioritize' '
	reprior_filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pfill sleep inf) &&
	flux job wait-event -t 5 ${reprior_filler} alloc &&
	reprior_trigger=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=psweep sleep inf) &&
	flux job wait-event -t 5 ${reprior_trigger} priority &&
	reprior_b_sched=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=psweep sleep inf) &&
	flux job wait-event -t 5 ${reprior_b_sched} priority
'

test_expect_success 'both associations have held jobs for reprioritize' '
	reprior_a_held=$(flux python ${SUBMIT_AS} 50001 \
		-N1 --dependency=afterany:${reprior_filler} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${reprior_a_held} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${reprior_a_held} dependency-add &&
	reprior_b_held=$(flux python ${SUBMIT_AS} 50002 \
		-N1 --dependency=afterany:${reprior_b_sched} \
		--queue=psweep sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${reprior_b_held} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${reprior_b_held} dependency-add
'

test_expect_success 'raise psweep queue limit before reprioritize' '
	flux python psweep_queue_update.py 2 &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.psweep.max_sched_nodes_per_assoc == 2" <query.json &&
	jq -e ".queues.psweep.max_sched_cores_per_assoc == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'reprioritize releases held jobs from both associations' '
	flux python <<-EOF &&
	import flux
	flux.Flux().rpc("job-manager.mf_priority.reprioritize").get()
	EOF
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${reprior_a_held} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${reprior_a_held} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-nodes-queue-limit" \
		${reprior_b_held} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-cores-queue-limit" \
		${reprior_b_held} dependency-remove
'

test_expect_success 'cancel reprioritize sweep jobs' '
	flux cancel ${reprior_a_held} ${reprior_b_held} &&
	flux job wait-event -t 5 ${reprior_a_held} clean &&
	flux job wait-event -t 5 ${reprior_b_held} clean &&
	flux cancel ${reprior_filler} ${reprior_trigger} ${reprior_b_sched} &&
	flux job wait-event -t 5 ${reprior_filler} clean &&
	flux job wait-event -t 5 ${reprior_trigger} clean &&
	flux job wait-event -t 5 ${reprior_b_sched} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python <<-EOF
	import flux
	flux.Flux().rpc("accounting.shutdown_service").get()
	EOF
'

test_done
