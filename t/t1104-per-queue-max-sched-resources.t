#!/bin/bash

test_description='test enforcing the per-queue total max-nodes/cores limit'

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

# Setting max-nodes and max-cores to 4 means that across *all*
# associations, the "pdebug" queue can have up to 4 nodes and 4 cores in a
# non-terminal (SCHED or RUN) state at any given time.
test_expect_success 'add a queue to DB' '
	flux account add-queue pdebug \
		--max-nodes=4 \
		--max-cores=4
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add two associations under the same bank/queue' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug \
		--max-active-jobs=10000 \
		--max-running-jobs=1000 &&
	flux account add-user \
		--username=user2 \
		--bank=A \
		--userid=50002 \
		--queues=pdebug \
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
	[queues.pdebug]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'queue-total limits are configured in plugin' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.pdebug.max_nodes == 4" <query.json &&
	jq -e ".queues.pdebug.max_cores == 4" <query.json
'

# user1's job takes up all resources of the instance and consumes the entire
# queue's available resources (4 nodes / 4 cores).
test_expect_success 'user1 job proceeds to RUN immediately' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

# user2 shares the queue-wide total, so even a single-node job gets held on the
# queue-total dependencies
test_expect_success 'user2 job holds on queue-total dependencies' '
	job2=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${job2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${job2} dependency-add
'

test_expect_success 'queue-total held job is tracked under user2' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 1" <query.json
'

# Cancelling user1's running job decrements the queue-wide total, and the
# cross-association release sweep re-examines user2's held job in this queue.
test_expect_success 'cancel user1 job; user2 held job releases and runs' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${job2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${job2} dependency-remove &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job2' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

test_expect_success 'no held jobs remain for either association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 0" <query.json
'

# verify the queue-total counter tracks non-terminal jobs across a plugin
# reload: a running job keeps the queue-wide total occupied, so a job submitted
# after the reload still sees the limit.
test_expect_success 'submit a running job that occupies the queue total' '
	rjob=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${rjob} alloc
'

test_expect_success 'reload plugin' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'queue-total counter re-established after reload' '
	held=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${held} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${held} dependency-add
'

test_expect_success 'cancel running job; held job releases across reload' '
	flux cancel ${rjob} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${held} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${held} dependency-remove &&
	flux job wait-event -t 5 ${held} alloc
'

test_expect_success 'cancel held job' '
	flux cancel ${held} &&
	flux job wait-event -t 5 ${held} clean
'

# A job that is *already held* on the queue-total dependencies must remain held
# across a plugin reload. On reload, active jobs are re-seen in reverse state
# order, so the running job re-populates the queue-wide counter (via job.new)
# before the held job's job.state.depend callback re-evaluates -- otherwise the
# held job would spuriously release.
test_expect_success 'set up a running job and a job held on queue-total deps' '
	rjob2=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${rjob2} alloc &&
	held2=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${held2} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${held2} dependency-add
'

test_expect_success 'reload plugin' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'held job is still held after reload' '
	held2_dec=$(flux job id -t dec ${held2}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"${held2_dec}\"].deps | length == 2" <query.json &&
	test_must_fail flux job wait-event -t 2 ${held2} alloc
'

test_expect_success 'held job releases once running job is cancelled' '
	flux cancel ${rjob2} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${held2} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${held2} dependency-remove &&
	flux job wait-event -t 5 ${held2} alloc
'

test_expect_success 'cancel jobs' '
	flux cancel ${held2} &&
	flux job wait-event -t 5 ${held2} clean
'

# If an association has two held jobs of different sizes and freeing a running
# job leaves only enough queue headroom for the smaller one, the plugin must
# iterate past the larger held job (which still does not fit) and release the
# smaller one. Two -N2 jobs fill the queue total of 4.
test_expect_success 'fill the queue total with two running jobs' '
	fitA=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${fitA} alloc &&
	fitB=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${fitB} alloc
'

# big is submitted before small, so it sits earlier in the held_jobs vector and
# is evaluated first when the release sweep runs.
test_expect_success 'submit a large then a small job; both held on queue-total' '
	big=$(flux python ${SUBMIT_AS} 50002 -N3 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${big} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${big} dependency-add &&
	small=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${small} dependency-add &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${small} dependency-add
'

# Cancel one -N2 job: queue headroom becomes 2 nodes/cores. The larger held job
# (-N3) still does not fit (2 + 3 > 4) and stays held, but the smaller held job
# (-N1) fits (2 + 1 <= 4) and is released, proving the sweep skips the larger
# job and continues to a releasable one.
test_expect_success 'freeing partial headroom releases only the smaller job' '
	flux cancel ${fitB} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${small} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${small} dependency-remove &&
	flux job wait-event -t 5 ${small} alloc
'

test_expect_success 'larger job remains held on both queue-total deps' '
	big_dec=$(flux job id -t dec ${big}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50002) |
		 .banks[0].held_jobs[\"${big_dec}\"].deps | length == 2" <query.json &&
	test_must_fail flux job wait-event -t 2 ${big} alloc
'

test_expect_success 'cancelling fitA frees up headroom for big job' '
	flux cancel ${fitA} &&
	flux job wait-event -t 5 \
		--match-context=description="max-nodes-queue-total-limit" \
		${big} dependency-remove &&
	flux job wait-event -t 5 \
		--match-context=description="max-cores-queue-total-limit" \
		${big} dependency-remove &&
	flux job wait-event -t 5 ${big} alloc
'

test_expect_success 'cancel jobs' '
	flux cancel ${big} ${small} &&
	flux job wait-event -t 5 ${big} clean &&
	flux job wait-event -t 5 ${small} clean
'

# Setting the limit to -1 (unlimited) means jobs never hold on the queue-total
# dependency regardless of how many resources are committed.
test_expect_success 'reset queue-total limits to unlimited' '
	flux account edit-queue pdebug \
		--max-nodes=-1 \
		--max-cores=-1 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'a job does not hold on queue-total deps when unlimited' '
	ujob1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${ujob1} alloc &&
	ujob2=$(flux python ${SUBMIT_AS} 50002 -N1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 5 ${ujob2} priority &&
	test_must_fail flux job wait-event -t 2 \
		--match-context=description="max-nodes-queue-total-limit" \
		${ujob2} dependency-add
'

test_expect_success 'cancel jobs' '
	flux cancel ${ujob1} ${ujob2} &&
	flux job wait-event -t 5 ${ujob1} clean &&
	flux job wait-event -t 5 ${ujob2} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
