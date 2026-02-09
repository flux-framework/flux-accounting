#!/bin/bash

test_description='test enforcing per-queue resource limits'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py

mkdir -p config

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze --max-nodes-per-assoc=1 &&
	flux account add-queue silver --max-nodes-per-assoc=2 &&
	flux account add-queue gold --max-nodes-per-assoc=3
'

test_expect_success 'add an association to the DB' '
	flux account add-user --username=user1 \
		--userid=50001 \
		--bank=A \
		--max-running-jobs=2 \
		--max-active-jobs=100 \
		--max-nodes=10 \
		--max-cores=100 \
		--queues=bronze,silver,gold
'

test_expect_success 'configure flux with those queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

# Scenario 1: An association submits a 1-node job to the bronze queue, which
# has a max_nodes limit of 1. A second-submitted job to the bronze queue will
# be held with a queue-specific max resources dependency. 
test_expect_success 'submit a job to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc
'

test_expect_success 'check resource counts for association in bronze queue' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'hold second job due to per-queue max nodes limit' '
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'second job gets released when first job completes' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job2} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'cancel second job' '
	flux cancel ${job2}
'

# Scenario 2: An association submits a 1-node job to the bronze queue, which
# has a max_nodes limit of 1. The association's properties are also edited to
# have a max_nodes limit of 1. A second-submitted job to the bronze queue will
# be held with BOTH a queue-specific max_nodes_per_assoc dependency AND a
# per-association max resources dependency.
test_expect_success 'edit association max_nodes limit to 1' '
	flux account edit-user user1 --max-nodes=1
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc
'

test_expect_success 'check resource counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'hold second job due to queue and association limits' '
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'second job gets released when first job completes' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job2} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'cancel second job' '
	flux cancel ${job2}
'

# Scenario 3: An association submits a 1-node job to the bronze queue, which
# has a max_nodes limit of 1 AND a max_running_jobs limit of 1. A
# second-submitted job to the bronze queue will be held with the following
# dependencies:
#   - queue-specific max_nodes_per_assoc
#   - queue-specific max_running_jobs
#   - association-specific max_nodes
test_expect_success 'edit queue max_running_jobs limit to 1' '
	flux account edit-queue bronze --max-running-jobs=1
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc
'

test_expect_success 'check resource counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'second job is held due to multiple limits being hit' '
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'second job gets released when first job completes' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job2} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 0" <query.json
'

test_expect_success 'cancel second job' '
	flux cancel ${job2}
'

# Scenario 4: An association submits a 1-node job to the bronze queue, which
# has a max_nodes limit of 1 AND a max_running_jobs limit of 1. The
# association's properties are also edited to have a max running jobs limit of
# 1. A second-submitted job to the bronze queue will be held with the following
# dependencies:
#   - queue-specific max_nodes
#   - queue-specific max_running_jobs
#   - association-specific max_nodes
#   - association-specific max_running_jobs
test_expect_success 'edit association max_running_jobs limit to 1' '
	flux account edit-user user1 --max-running-jobs=1
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc
'

test_expect_success 'check resource counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'second job is held due to multiple limits being hit' '
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-add &&
	flux job wait-event -vt 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'second job gets released when first job completes' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 ${job2} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 0" <query.json
'

test_expect_success 'cancel second job' '
	flux cancel ${job2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
