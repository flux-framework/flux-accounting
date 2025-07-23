#!/bin/bash

test_description='test tracking per-queue resource usage'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py

mkdir -p config

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
	flux account add-queue bronze &&
	flux account add-queue silver
'

test_expect_success 'configure flux with those queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'add an association to the DB' '
	flux account add-user --username=user1 \
		--userid=50001 \
		--bank=A \
		--queues=bronze,silver
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

# The association's usage will be 1 node total in just the bronze queue.
test_expect_success 'submit a 1-node job to bronze queue' '
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

test_expect_success 'cancel job' '
	flux cancel ${job1}
'

# The association's usage will be 2 nodes total in just the bronze queue.
test_expect_success 'submit 2 1-node jobs to bronze queue' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job2} alloc
'

test_expect_success 'check resource counts for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 2" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2}
'

# The association's usage will be 5 nodes total in both the bronze and silver
# queue; 1 node in the bronze queue, and 4 in the silver queue.
test_expect_success 'submit 2 different-sized jobs to multiple queues' '
	job1=$(flux python ${SUBMIT_AS} 50001 --queue=bronze -N1 sleep 60) &&
	flux job wait-event -vt 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 --queue=silver -N4 sleep 60) &&
	flux job wait-event -vt 5 ${job2} alloc
'

test_expect_success 'check resource counts in bronze queue for association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 5" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"bronze\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'check resource counts in silver queue for association' '
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"silver\"].cur_nodes == 4" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"silver\"].cur_run_jobs == 1" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
