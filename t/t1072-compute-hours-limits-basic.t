#!/bin/bash

test_description='test loading compute hours limit plugin'

. `dirname $0`/sharness.sh

COMPUTE_HOURS_LIMITS=${FLUX_BUILD_DIR}/src/plugins/.libs/compute_hours_limits.so
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

test_expect_success 'load compute hours limits plugin' '
	flux jobtap load ${COMPUTE_HOURS_LIMITS}
'

test_expect_success 'check to see if plugin is loaded' '
	flux jobtap list | grep compute_hours_limits
'

test_expect_success 'add data to flux-accounting DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=50001 --bank=A
'

test_expect_success 'send flux-accounting DB data to plugin' '
	flux account-compute-hours-update -p ${DB_PATH}
'

# The expected usage U for this job is as follows:
# U = job.nnodes * job.requested_duration = 4 * 3600 = 14400
test_expect_success 'submit a job' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 -n8 -S duration=3600 sleep 60) &&
	flux job wait-event --quiet -t 3 ${job1} alloc
'

# The current usage should show the anticipated max while the job is running.
test_expect_success 'check current usage of association' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 14400" <query.json
'

# The job and its attributes should be stored in the Association's "jobs" map.
test_expect_success 'ensure "jobs" map knows of active job' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 1" <query.json
'

test_expect_success 'cancel job' '
	flux cancel ${job1} &&
	flux job wait-event -t 3 ${job1} clean
'

# Now that the job is cancelled and the association has no active jobs, the
# current usage is reflected to no current usage.
test_expect_success 'ensure current usage is 0' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 0" <query.json
'

# After the job is cleaned up, the total usage is updated to show the job's
# actual usage.
test_expect_success 'ensure total usage is updated to show completed job' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].total_usage > 0 and .banks[0].total_usage < 14400" <query.json
'

# Once the job has completed, it is removed from the association's "jobs" map.
test_expect_success 'ensure "jobs" map is cleared of completed job' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 0" <query.json
'

# The expected usage for the following three jobs are calculated as follows:
# U_job1 = 1 * 60 = 60
# U_job2 = 1 * 60 = 60
# U_job3 = 1 * 60 = 60
test_expect_success 'submit three jobs' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N1 -S duration=60 sleep 60) &&
	job2=$(flux python ${SUBMIT_AS} 50001 -N1 -S duration=60 sleep 60) &&
	job3=$(flux python ${SUBMIT_AS} 50001 -N1 -S duration=60 sleep 60) &&
	flux job wait-event -t 3 ${job1} alloc &&
	flux job wait-event -t 3 ${job2} alloc &&
	flux job wait-event -t 3 ${job3} alloc
'

# The current usage should show the anticipated max usage of all running jobs.
test_expect_success 'check current usage of association' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 180" <query.json
'

# The job and its attributes should be stored in the Association's "jobs" map.
test_expect_success 'ensure "jobs" map knows of all active jobs' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 3" <query.json
'

# As jobs complete, the current_usage for the Association is updated to reflect
# only currently running jobs. The total_usage gets updated with the job's
# actual duration once it transitions to job.state.inactive.
test_expect_success 'cancel job1' '
	flux cancel ${job1}
'

test_expect_success 'ensure current usage gets updated' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 120" <query.json &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 2" <query.json
'

test_expect_success 'cancel job2' '
	flux cancel ${job2}
'

test_expect_success 'ensure current usage gets updated' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 60" <query.json &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 1" <query.json
'

test_expect_success 'cancel job3' '
	flux cancel ${job3}
'

# Store the total usage for the association up to this point in a variable
# called total_usage, which will be used for a test later on.
test_expect_success 'ensure current usage gets updated' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].current_usage == 0" <query.json &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs | length == 0" <query.json &&
	total_usage=$(jq -r \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].total_usage" <query.json)
'

test_expect_success 'submit a job that never runs' '
	job1=$(flux python ${SUBMIT_AS} 50001 \
		-N1 -S duration=60 --urgency=0 sleep 60) &&
	flux job wait-event -t 3 ${job1} priority
'

test_expect_success 'check expected usage for association' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].jobs[\"$(flux job id -t dec ${job1})\"] |
		 .expected_usage == 60" <query.json
'

test_expect_success 'cancel job' '
	flux cancel ${job1} &&
	flux job wait-event -t 3 ${job1} clean
'

# A job that never runs should not affect an association's total usage.
test_expect_success 'ensure total_usage remains the same after cancellation' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].total_usage == ${total_usage}" <query.json
'

test_expect_success 'send "clear" rpc to compute_hours_plugin' '
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.compute_hours_limits.clear\")"
'

test_expect_success 'check total_usage attribute of association after "clear" rpc' '
	flux jobtap query compute_hours_limits.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".compute_hours_limits[] |
		 select(.userid == 50001) |
		 .banks[0].total_usage == 0.0" <query.json
'

test_done
