#!/bin/bash

test_description='resolve queue-held jobs when association data arrives late'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
userid=$(id -u)

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -Slog-stderr-level=1

test_expect_success 'configure named queue' '
	flux config load <<-EOF &&
	[queues.late]
	EOF
	flux queue start --all
'

# send individual payloads without the automatic reprioritize performed by
# account-priority-update, so the arrival order is deterministic
test_expect_success 'create accounting payload helper' '
	cat >update.py <<-EOF
	import json
	import os
	import sys

	import flux


	def association(userid, bank, max_run):
	    return {
	        "userid": userid,
	        "bank": bank,
	        "def_bank": "A",
	        "fairshare": 0.5,
	        "max_running_jobs": max_run,
	        "max_active_jobs": 100,
	        "max_nodes": 2147483647,
	        "max_cores": 2147483647,
	        "max_sched_jobs": 2147483647,
	        "queues": "late",
	        "active": 1,
	        "projects": "*",
	        "def_project": "*",
	    }


	def queue(max_run):
	    return {
	        "queue": "late",
	        "priority": 0,
	        "max_running_jobs": max_run,
	        "max_sched_jobs": 2147483647,
	        "max_sched_nodes_per_assoc": 2147483647,
	        "max_sched_cores_per_assoc": 2147483647,
	    }


	mode = sys.argv[1]
	if mode == "initial":
	    print(json.dumps({
	        "associations": [association(os.getuid(), "keeper", 100)],
	        "queues": [queue(0)],
	    }))
	elif mode == "queue":
	    flux.Flux().rpc("job-manager.mf_priority.rec_q_update", {
	        "data": [queue(int(sys.argv[2]))],
	    }).get()
	elif mode == "association":
	    flux.Flux().rpc("job-manager.mf_priority.rec_update", {
	        "data": [association(os.getuid(), sys.argv[2], int(sys.argv[3]))],
	    }).get()
	elif mode == "reprioritize":
	    flux.Flux().rpc("job-manager.mf_priority.reprioritize").get()
	EOF
'

test_expect_success 'submit jobs with default and explicit banks in DEPEND' '
	anchor=$(flux submit --queue=late --setattr=bank=keeper \
		--setattr=project=* sleep inf) &&
	flux job wait-event -t 15 ${anchor} alloc &&
	a1=$(flux submit --queue=late \
		--dependency=afterany:${anchor} sleep inf) &&
	a2=$(flux submit --queue=late \
		--dependency=afterany:${anchor} sleep inf) &&
	b1=$(flux submit --queue=late --setattr=bank=B \
		--dependency=afterany:${anchor} sleep inf) &&
	b2=$(flux submit --queue=late --setattr=bank=B \
		--dependency=afterany:${anchor} sleep inf) &&
	for id in ${a1} ${a2} ${b1} ${b2}; do
		flux job wait-event -t 15 ${id} dependency-add || return 1
	done
'

# Only the already-running job has association data at plugin load. The
# four DEPEND jobs share the "DNE" and acquire holds from the known queue limit
test_expect_success 'replay jobs with queue limits but no user association' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux python update.py initial)" &&
	for id in ${a1} ${a2} ${b1} ${b2}; do
		flux job wait-event -t 15 \
			--match-context=description=max-run-jobs-queue \
			${id} dependency-add || return 1
	done &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		(.held_jobs | length) == 4 and .cur_active_jobs == 0" query.json
'

test_expect_success 'queue update alone cannot release unresolved jobs' '
	flux python update.py queue 2 &&
	flux python update.py reprioritize &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		(.held_jobs | length) == 4" query.json
'

test_expect_success 'receiving one bank does not release or migrate jobs yet' '
	flux python update.py association A 0 &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		(.held_jobs | length) == 4" query.json
'

test_expect_success 'resolve default-bank jobs and enforce newly known limit' '
	flux python update.py reprioritize &&
	for id in ${a1} ${a2}; do
		flux job wait-event -t 15 \
			--match-context=description=max-running-jobs-user-limit \
			${id} dependency-add || return 1
	done &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"A\") |
		(.held_jobs | length) == 2 and .cur_active_jobs == 2" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		(.held_jobs | length) == 2 and .cur_active_jobs == 0" query.json &&
	flux job info ${a2} eventlog >eventlog.json &&
	jq -se "any(.[]; .name == \"jobspec-update\" and
		.context[\"attributes.system.bank\"] == \"A\" and
		.context[\"attributes.system.project\"] == \"*\")" eventlog.json
'

test_expect_success 'repeated updates neither duplicate holds nor charges' '
	flux python update.py association A 0 &&
	flux python update.py reprioritize &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"A\") |
		(.held_jobs | length) == 2 and .cur_active_jobs == 2" query.json &&
	flux job info ${a2} eventlog >eventlog.json &&
	jq -se "[.[] | select(.name == \"dependency-add\" and
		.context.description == \"max-running-jobs-user-limit\")] |
		length == 1" eventlog.json
'

test_expect_success 'resolve explicit bank during another job callback' '
	flux python update.py association B 100 &&
	trigger=$(flux submit --queue=late --setattr=bank=keeper true) &&
	flux job wait-event -t 15 ${trigger} clean &&
	for id in ${b1} ${b2}; do
		flux job wait-event -t 15 \
			--match-context=description=max-run-jobs-queue \
			${id} dependency-remove || return 1
	done &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"B\") |
		(.held_jobs | length) == 0 and .cur_active_jobs == 2 and
		.cur_sched_jobs == 0 and .cur_run_jobs == 0" query.json &&
	flux job info ${b1} eventlog >eventlog.json &&
	jq -se "all(.[]; .name != \"depend\") and
		any(.[]; .name == \"jobspec-update\" and
			.context[\"attributes.system.project\"] == \"*\")" eventlog.json
'

test_expect_success 'cancelling a transferred held job removes its charge' '
	flux cancel ${a1} &&
	flux job wait-event -t 15 ${a1} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"A\") |
		(.held_jobs | length) == 1 and .cur_active_jobs == 1" query.json
'

test_expect_success 'raising association limit releases remaining accounting hold' '
	flux python update.py association A 1 &&
	flux python update.py reprioritize &&
	flux job wait-event -t 15 \
		--match-context=description=max-running-jobs-user-limit \
		${a2} dependency-remove &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		(.held_jobs | length) == 0 and .cur_active_jobs == 0" query.json
'

test_expect_success 'resolved jobs reach RUN when the unrelated hold clears' '
	flux cancel ${anchor} &&
	flux job wait-event -t 15 ${anchor} clean &&
	for id in ${a2} ${b1} ${b2}; do
		flux job wait-event -t 15 ${id} alloc || return 1
	done
'

test_expect_success 'cleanup leaves no held entries or usage in either bank' '
	flux cancel ${a2} ${b1} ${b2} &&
	for id in ${a2} ${b1} ${b2}; do
		flux job wait-event -t 15 ${id} clean || return 1
	done &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		all(.banks[]; (.held_jobs | length) == 0 and
			.cur_active_jobs == 0 and .cur_run_jobs == 0 and
			.cur_sched_jobs == 0 and .cur_nodes == 0 and .cur_cores == 0 and
			all(.queue_usage[]; .cur_run_jobs == 0 and .cur_sched_jobs == 0 and
				.cur_sched_nodes == 0 and .cur_sched_cores == 0))" query.json
'

test_done
