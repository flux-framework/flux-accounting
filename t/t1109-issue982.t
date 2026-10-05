#!/bin/bash

test_description='ensure SCHED reservation transfers on job update'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

mf_priority_counters_nonnegative() {
	flux jobtap query mf_priority.so >counters.json &&
	jq -e "[.. | objects | to_entries[] |
		select(.key | startswith(\"cur_\")) | .value | numbers] |
		all(. >= 0)" counters.json
}

mf_priority_quiescent() {
	flux jobtap query mf_priority.so >counters.json &&
	jq -e "[.. | objects | to_entries[] |
		select(.key | startswith(\"cur_\")) | .value | numbers] |
		all(. == 0)" counters.json &&
	jq -e "[.mf_priority_map[].banks[].held_jobs | length] |
		all(. == 0)" counters.json
}

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

test_expect_success 'add queues to DB' '
	flux account add-queue pbatch --max-nodes-per-assoc=2 &&
	flux account add-queue pdebug --max-nodes-per-assoc=2 &&
	flux account add-queue standby
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add an association to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pbatch,pdebug,standby \
		--max-nodes=100 \
		--max-cores=100 \
		--max-active-jobs=1000 \
		--max-running-jobs=1000 &&
	flux account add-user \
		--username=user1 \
		--bank=B \
		--userid=50001 \
		--queues=pbatch,pdebug,standby \
		--max-nodes=100 \
		--max-cores=100 \
		--max-active-jobs=1000 \
		--max-running-jobs=1000
'

test_expect_success 'load and initialize priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'configure flux with queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.pbatch]
	[queues.pdebug]
	[queues.standby]
	EOT
	flux config reload &&
	flux queue start --all
'

# Keep all physical nodes allocated so the test job remains in SCHED while its
# queue is updated
test_expect_success 'filler job in standby soaks all physical nodes' '
	filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=standby sleep inf) &&
	flux job wait-event -t 5 ${filler} alloc
'

test_expect_success 'job1 enters SCHED state in pbatch' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N2 -n4 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${job1} priority
'

test_expect_success 'job1 is counted in SCHED for pbatch' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_nodes == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_cores == 4" <query.json
'

test_expect_success 'job2 is held by current pbatch SCHED usage' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 -n2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add
'

# The job is counted in pbatch, then its queue is updated *before* the job
# leaves SCHED
test_expect_success 'update SCHED job from pbatch to pdebug' '
	flux update ${job1} queue=pdebug &&
	flux job wait-event -t 5 \
		--match-context=attributes.system.queue=pdebug \
		${job1} jobspec-update
'

test_expect_success 'held pbatch job is released after SCHED usage transfer' '
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-remove
'

test_expect_success 'updated SCHED job is counted in pdebug' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_jobs == 1" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_nodes == 1" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_cores == 2" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_jobs == 1" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_nodes == 2" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_cores == 4" \
		<query.json
'

test_expect_success 'clean up released pbatch job' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

test_expect_success 'cancel updated SCHED job' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'updated job leaves no stale SCHED queue usage in pbatch' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_jobs == 0" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_nodes == 0" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pbatch\"].cur_sched_cores == 0" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_jobs == 0" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_nodes == 0" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_sched_cores == 0" \
		<query.json
'

test_expect_success 'fresh pbatch job is not held by stale queue usage' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${job3} priority &&
	test_must_fail flux job wait-event -t 1 \
		--match-context=description="max-resources-queue" \
		${job3} dependency-add
'

test_expect_success 'clean up fresh pbatch job' '
	flux cancel ${job3} &&
	flux job wait-event -t 5 ${job3} clean
'

# This set of tests makes sure that updating the bank on a job does not
# leave stale usage in the old bank
test_expect_success 'job4 enters SCHED state under bank A' '
	job4=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${job4} priority
'

test_expect_success 'job4 is counted in SCHED for bank A' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .queue_usage[\"pbatch\"].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .queue_usage[\"pbatch\"].cur_sched_nodes == 2" <query.json
'

# The job is counted in bank A, then its bank is updated *before* the job
# leaves SCHED
test_expect_success 'update SCHED job from bank A to bank B' '
	flux update ${job4} bank=B &&
	flux job wait-event -t 5 \
		--match-context=attributes.system.bank=B \
		${job4} jobspec-update
'

test_expect_success 'updated SCHED job is counted under bank B' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .queue_usage[\"pbatch\"].cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .queue_usage[\"pbatch\"].cur_sched_nodes == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .queue_usage[\"pbatch\"].cur_sched_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .queue_usage[\"pbatch\"].cur_sched_nodes == 2" <query.json
'

test_expect_success 'cancel bank-updated SCHED job' '
	flux cancel ${job4} &&
	flux job wait-event -t 5 ${job4} clean
'

test_expect_success 'bank-updated job leaves no stale SCHED usage' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"A\") |
		 .queue_usage[\"pbatch\"].cur_sched_nodes == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .queue_usage[\"pbatch\"].cur_sched_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .queue_usage[\"pbatch\"].cur_sched_nodes == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[] |
		 select(.bank_name == \"B\") |
		 .queue_usage[\"pbatch\"].cur_sched_cores == 0" <query.json
'

test_expect_success 'clean up jobs' '
	flux cancel ${filler}
'

# This set of tests makes sure that a job is checked to see if it's eligible
# for release after being updated.
test_expect_success 'filler job in standby takes up all physical nodes' '
	filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=standby sleep inf) &&
	flux job wait-event -t 5 ${filler} alloc
'

test_expect_success 'job1 enters SCHED state in pbatch' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${job1} priority
'

test_expect_success 'job2 is held by pbatch max-resources-queue' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add
'

test_expect_success 'plugin tracks job2 as held in pbatch' '
	job2_dec=$(flux job id -t dec ${job2}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job2_dec}\"].queue == \"pbatch\"" \
		<query.json
'

test_expect_success 'update held job2 from pbatch to pdebug' '
	flux update ${job2} queue=pdebug &&
	flux job wait-event -t 5 \
		--match-context=attributes.system.queue=pdebug \
		${job2} jobspec-update
'

test_expect_success 'held accounting dependency is removed after queue update' '
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-remove
'

test_expect_success 'plugin no longer tracks job2 as held' '
	job2_dec=$(flux job id -t dec ${job2}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'clean up jobs' '
	flux cancel ${job1} ${job2} ${filler} &&
	flux job wait-event -t 5 ${job1} clean &&
	flux job wait-event -t 5 ${job2} clean &&
	flux job wait-event -t 5 ${filler} clean
'

test_expect_success 'filler job in standby takes up all physical nodes' '
	filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=standby sleep inf) &&
	flux job wait-event -t 5 ${filler} alloc
'

test_expect_success 'urgency change of SCHED job does not double count' '
	job=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pbatch sleep inf) &&
	flux job wait-event -t 5 ${job} priority &&
	flux job urgency ${job} 20 &&
	flux job wait-event -t 5 --count=2 ${job} priority &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 50001) |
		.banks[0].queue_usage[\"pbatch\"].cur_sched_jobs == 1" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 50001) |
		.banks[0].queue_usage[\"pbatch\"].cur_sched_nodes == 2" query.json
'

test_expect_success 'clean up jobs' '
	flux cancel ${filler} ${job} &&
	flux job wait-event -t 5 ${filler} clean &&
	flux job wait-event -t 5 ${job} clean
'

test_expect_success 'plugin is in clean state after cleanup' '
	mf_priority_counters_nonnegative &&
	mf_priority_quiescent
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
