#!/bin/bash

test_description='test managing dependencies with plugin DB initialization'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

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

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add associations' '
	flux account add-user \
		--username=user1 --bank=A --userid=50001 \
		--max-running-jobs=1 --max-active-jobs=2
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'ensure association is in priority plugin data structure' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_active_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_run_jobs == 1" <query.json
'

# In this set of tests, we make sure that an association who has hit their max
# running jobs per-association limit preserves this same limit after a plugin
# reload.
test_expect_success 'submit 2 jobs to trigger max-run-jobs per-association limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job2} dependency-add
'

test_expect_success 'reload plugin with sort order' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'look at job counts for association' '
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
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'cancel job1' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'job2 gets alloc event now that association under limit' '
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job2} dependency-remove
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job2' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

# In this set of tests, we make sure that an association who has hit their max
# resource per-association limit preserves this same limit after a plugin reload.
test_expect_success 'edit association resource limits' '
	flux account edit-user user1 --max-running-jobs=-1 --max-active-jobs=-1 \
		--max-nodes=1
'

test_expect_success 'update priority plugin with new association values' '
	flux account-priority-update -p ${DB}
'

test_expect_success 'resource limits for association are now updated' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_nodes == 1" <query.json
'

test_expect_success 'submit 2 jobs to trigger max-resource per-association limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add
'

test_expect_success 'reload plugin with sort order' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'look at job counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'cancel job1' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'job2 gets alloc event now that association under limit' '
	flux job wait-event -t 5 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-remove
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job2' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

# This set of tests checks that the per-queue max running jobs limits are
# preserved with a plugin reload.
test_expect_success 'add a queue to the flux-accounting DB' '
	flux account add-queue pdebug --max-running-jobs=1 &&
	flux account edit-user user1 --max-nodes=-1 --queues=pdebug
'

test_expect_success 'plugin successfully gets data update' '
	flux account-priority-update -p ${DB} &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.pdebug.name == \"pdebug\"" <query.json &&
	jq -e ".queues.pdebug.max_running_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queues[0] == \"pdebug\"" <query.json
'

test_expect_success 'configure flux with pdebug queue' '
	cat >config/queues.toml <<-EOT &&
	[queues.pdebug]
	[policy.jobspec.defaults.system]
	queue = "pdebug"
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'submit 2 jobs to trigger per-queue max-run-jobs limit' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-add
'

test_expect_success 'reload plugin with sort order' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'held job properly tracked with association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'cancel job1' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'job2 gets alloc event now that association under limit' '
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${job2} dependency-remove
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job2' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

# This set of tests checks that the per-queue max resource limits are
# preserved with a plugin reload.
test_expect_success 'edit max nodes per-association for pdebug' '
	flux account edit-queue pdebug --max-running-jobs=-1 --max-nodes-per-assoc=1 &&
	flux account-priority-update -p ${DB} &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.pdebug.max_nodes_per_assoc == 1" <query.json
'

test_expect_success 'max nodes per-association per-queue limit gets triggered' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-add
'

test_expect_success 'held job properly tracked with association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage.pdebug.cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'reload plugin with sort order' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'cancel job1' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'job2 gets alloc event now that association under limit' '
	flux job wait-event -t 5 \
		--match-context=description="max-resources-queue" \
		${job2} dependency-remove
	flux job wait-event -t 5 ${job2} alloc
'

test_expect_success 'cancel job2' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job2} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
