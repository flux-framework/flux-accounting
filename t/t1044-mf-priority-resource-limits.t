#!/bin/bash

test_description='track and enforce resource limits across running jobs per-association in priority plugin'

. `dirname $0`/sharness.sh

mkdir -p conf.d

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association, configure limits' '
	flux account add-user \
		--username=user1 --userid=5001 --bank=A \
		--max-active-jobs=1000 --max-running-jobs=3 \
		--max-nodes=2 --max-cores=4
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit 2 jobs that take up 1 node each; check resource counts' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -f json ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -f json ${job2} priority &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 2" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_cores == 2" <query.json
'

test_expect_success 'cancel jobs; check resource counts' '
	flux cancel ${job1} &&
	flux job wait-event -f json ${job1} clean &&
	flux cancel ${job2} &&
	flux job wait-event -f json ${job2} clean &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 0" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_cores == 0" <query.json
'

test_expect_success 'submit a job that takes up one core' '
	job3=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -f json ${job3} priority &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 0" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_cores == 1" <query.json
'

test_expect_success 'cancel job; check resource counts' '
	flux cancel ${job3} &&
	flux job wait-event -f json ${job3} clean &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 0" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_cores == 0" <query.json
'

# The following scenarios test tracking and enforcing limits on an association
# who has the following limits configured:
# max-running-jobs = 3
# max-nodes = 2
# max-cores = 4

# Scenario 1:
# In this set of tests, the association will submit enough jobs to take up
# their max nodes limit. If they submit a job that looks to take up at least
# one node, the job will be held with a "max-resource-user-limit" until one of
# the currently running jobs completes.
test_expect_success 'submit enough jobs to take up max-nodes limit' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job2} priority
'

test_expect_success 'check resource counts of association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].max_nodes == 2" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 2" <query.json
'

test_expect_success 'trigger max-nodes limit for association' '
	job3=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-resource-user-limit" \
		${job3} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'held job released to RUN when association is under resource limit' '
	flux cancel ${job1} &&
	flux job wait-event -vt 10 ${job3} alloc
'

test_expect_success 'cancel rest of jobs' '
	flux cancel ${job2} &&
	flux cancel ${job3}
'

test_expect_success 'make sure association has no held jobs in their Association object' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 0" <query.json
'

# Scenario 2:
# The association submits enough jobs to take up the max-nodes limit, but they
# still have one core available to use, so they can submit a job that takes up
# the last core and it will run right away.
test_expect_success 'submit enough jobs to take up max-nodes limit' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 ${job2} priority
'

test_expect_success 'association still under resources limit, they can submit a core-only job' '
	job3=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job3} alloc
'

test_expect_success 'check resource counts of association' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].max_nodes == 2" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_nodes == 2" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].max_cores == 4" <query.json &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].cur_cores == 3" <query.json
'

test_expect_success 'cancel all of the running jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2} &&
	flux cancel ${job3}
'

test_expect_success 'make sure association has no held jobs in their Association object' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 0" <query.json
'

# Scenario 3:
# The association will submit jobs that do not take up all of their resources,
# but will take up their max-running-jobs limit. This ensures the right
# dependency is added.
test_expect_success 'submit enough jobs to take up max-running-jobs limit' '
	job1=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job3} priority
'

test_expect_success 'trigger max-running-jobs limit for association' '
	job4=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-running-jobs-user-limit" \
		${job4} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'cancel one of the running jobs; ensure held job receives alloc event' '
	flux cancel ${job1} &&
	flux job wait-event -vt 10 ${job4} alloc
'

test_expect_success 'cancel all jobs' '
	flux cancel ${job2} &&
	flux cancel ${job3} &&
	flux cancel ${job4}
'

test_expect_success 'make sure association has no held jobs in their Association object' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 0" <query.json
'

# Scenario 4:
# The association submits enough jobs to take up both resource and running
# jobs limits. The job will get both dependencies added to it since it hits
# both limits with the same job submission. If a currently running job is
# released but the held job will still put the association over their max
# resources limit, the job will continue to be held until enough resources
# are freed.
test_expect_success 'submit enough jobs to take up both limits' '
	job1=$(flux python ${SUBMIT_AS} 5001 -N2 -n2 sleep 60) &&
	flux job wait-event -vt 10 ${job1} priority &&
	job2=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 5001 -n1 sleep 60) &&
	flux job wait-event -vt 10 ${job3} priority
'

test_expect_success 'ensure both dependencies get added to job' '
	job4=$(flux python ${SUBMIT_AS} 5001 -N1 sleep 60) &&
	flux job wait-event -vt 10 \
		--match-context=description="max-running-jobs-user-limit" \
		${job4} dependency-add &&
	flux job wait-event -vt 10 \
		--match-context=description="max-resource-user-limit" \
		${job4} dependency-add &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 1" <query.json
'

test_expect_success 'if resources limit is still hit, job will not be released' '
	flux cancel ${job3} &&
	flux job wait-event -vt 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${job4} dependency-remove &&
	test $(flux jobs -no {state} ${job4}) = DEPEND
'

test_expect_success 'once enough resources have been freed up, job can transition to run' '
	flux cancel ${job1} &&
	flux job wait-event -vt 5 \
		--match-context=description="max-resource-user-limit" \
		${job4} dependency-remove &&
	flux job wait-event -vt 10 ${job4} alloc
'

test_expect_success 'cancel rest of running jobs' '
	flux cancel ${job2} &&
	flux cancel ${job4}
'

test_expect_success 'make sure association has no held jobs in their Association object' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | select(.userid == 5001) | .banks[0].held_jobs | length == 0" <query.json
'

test_done
