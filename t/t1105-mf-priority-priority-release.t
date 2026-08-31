#!/bin/bash

test_description='test releasing held jobs in priority order'

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

# max_running_jobs=1 so that a single freed run slot only fits one held job;
# this makes the release *order* observable
test_expect_success 'add an association to the DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug \
		--max-active-jobs=10000 \
		--max-running-jobs=1
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

# Scenario A: an admin expedites a later-submitted held job; it should be
# released ahead of the earlier-submitted one when a run slot frees up.
test_expect_success 'submit 3 jobs; 1 runs, 2 are held in DEPEND' '
	jobA1=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${jobA1} alloc &&
	jobA2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobA2} dependency-add &&
	jobA3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobA3} dependency-add
'

test_expect_success 'expedite the later-submitted held job (jobA3)' '
	flux job urgency ${jobA3} 31
'

# cancelling the runner frees one slot; the expedited job (jobA3) should win it
# even though jobA2 was submitted first
test_expect_success 'cancel runner; expedited jobA3 is released, jobA2 stays held' '
	flux cancel ${jobA1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobA3} dependency-remove &&
	flux jobtap query mf_priority.so > queryA.json &&
	test_debug "jq -S . <queryA.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <queryA.json &&
	jobA2_dec=$(flux job id -t dec ${jobA2}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${jobA2_dec}\"].deps[0] \
			== \"max-running-jobs-user-limit\"" <queryA.json
'

test_expect_success 'cancel scenario A jobs' '
	flux cancel ${jobA2} ${jobA3} &&
	flux job wait-event -t 5 ${jobA2} clean &&
	flux job wait-event -t 5 ${jobA3} clean
'

test_expect_success 'association has 0 jobs across all counts' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 0" <query.json
'

# Scenario B: with equal urgency, the priority tiebreak is jobid, so the
# earlier-submitted held job is released first
test_expect_success 'submit 3 jobs at equal urgency; 1 runs, 2 are held' '
	jobB1=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${jobB1} alloc &&
	jobB2=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobB2} dependency-add &&
	jobB3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobB3} dependency-add
'

test_expect_success 'cancel runner; earlier jobB2 is released, jobB3 stays held' '
	flux cancel ${jobB1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${jobB2} dependency-remove &&
	flux jobtap query mf_priority.so > queryB.json &&
	test_debug "jq -S . <queryB.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <queryB.json &&
	jobB3_dec=$(flux job id -t dec ${jobB3}) &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${jobB3_dec}\"].deps[0] \
			== \"max-running-jobs-user-limit\"" <queryB.json
'

test_expect_success 'cancel scenario B jobs' '
	flux cancel ${jobB2} ${jobB3} &&
	flux job wait-event -t 5 ${jobB2} clean &&
	flux job wait-event -t 5 ${jobB3} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
