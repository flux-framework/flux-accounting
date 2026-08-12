#!/bin/bash

test_description='test max-resources-queue counts jobs committed in SCHED state'

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

test_expect_success 'add queues to DB' '
	flux account add-queue bronze --max-nodes-per-assoc=2 &&
	flux account add-queue standby
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=bronze,standby \
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
	[queues.bronze]
	[queues.standby]
	EOT
	flux config reload &&
	flux queue start --all
'

# filler occupies every physical node so subsequent jobs cannot be allocated
# and must remain in SCHED state
test_expect_success 'filler job in standby soaks all physical nodes' '
	filler=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=standby sleep inf) &&
	flux job wait-event -t 5 ${filler} alloc
'


# job1 takes up all of the max_nodes_per_assoc limit in the bronze queue for
# user1
test_expect_success 'job1 enters SCHED state in bronze' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${job1} priority
'

test_expect_success 'job1 is counted in SCHED for bronze' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_sched_nodes == 2" <query.json
'

# With 2 nodes already committed to bronze (job1 in SCHED), job2 (another 2
# nodes) exceeds the cap and is held with a max-resources-queue dependency
test_expect_success 'job2 is held with max-resources-queue dependency' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add
'

# job1 keeps using 2 nodes when it transitions SCHED -> RUN, so job2 stays
# held; only when job1 transitions to INACTIVE does bronze free up for job2.
test_expect_success 'job1 running still holds job2; job1 done releases it' '
	flux cancel ${filler} &&
	flux job wait-event -t 5 ${job1} alloc &&
	test_must_fail flux job wait-event -t 2 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-remove &&
	flux cancel ${job1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-remove &&
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'clean up jobs' '
	flux cancel ${job2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
