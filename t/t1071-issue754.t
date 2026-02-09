#!/bin/bash

test_description='test ensuring held jobs are removed from Association object after cancellation'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

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

# In this first set of tests, the association has max_nodes and max_cores
# limits each set to just 1. The first job consumes both a node and a core, so
# the second job is held in DEPEND with max-resources-user-limit. The following
# set of tests ensure that cancelling the held job before it ever runs will
# remove it from the Association's list of held jobs.
test_expect_success 'add an association' '
	flux account add-user \
		--username=user1 \
		--userid=50001 \
		--bank=A \
		--max-nodes=1 \
		--max-cores=1
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB}
'

test_expect_success 'submit a job that takes up all resource limits' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 sleep inf) &&
	flux job wait-event -vt 3 ${job1} alloc
'

test_expect_success 'a second submitted job gets held with a resource limit' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 sleep inf) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 1" <query.json
'

test_expect_success 'cancel held job' '
	flux cancel ${job2} &&
	flux job wait-event -vt 3 ${job2} clean
'

test_expect_success 'make sure held job does not show up in Association object' '
	flux jobtap query mf_priority.so > query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 0" <query.json
'

test_expect_success 'cancel running job' '
	flux cancel ${job1} &&
	flux job wait-event -vt 3 ${job1} clean
'

# In this next scenario, 2 jobs are also submitted to repeat the scenario
# above. This time, both jobs are cancelled and a *third* job is submitted. The
# following set of tests makes sure that job 3 can proceed to RUN without
# getting held.
test_expect_success 'submit two jobs and ensure second one is held' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 sleep inf) &&
	flux job wait-event -vt 3 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 sleep inf) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-resources-user-limit" \
		${job2} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 1" <query.json
'

test_expect_success 'cancel both jobs' '
	flux cancel ${job1} ${job2} &&
	flux job wait-event -vt 3 ${job1} clean &&
	flux job wait-event -vt 3 ${job2} clean &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 0" <query.json
'

test_expect_success 'a third submitted job can proceed to RUN without issue' '
	job3=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 sleep inf) &&
	flux job wait-event -vt 3 ${job3} alloc &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs |
		 length == 0" <query.json
'

test_expect_success 'cancel third job' '
	flux cancel ${job3} &&
	flux job wait-event -vt 3 ${job3} clean
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
