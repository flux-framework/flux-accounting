#!/bin/bash

test_description='test validating and setting project names in priority plugin'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

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

test_expect_success 'add banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root account1 1
'

test_expect_success 'add projects to the DB' '
	flux account add-project projectA &&
	flux account add-project projectB &&
	flux account add-project projectC
'

test_expect_success 'submit jobs under two different users before plugin gets updated' '
	job_project_star=$(flux python ${SUBMIT_AS} 5001 hostname) &&
	job_project_A=$(flux python ${SUBMIT_AS} 5002 hostname) &&
	flux job wait-event -vt 60 $job_project_star depend &&
	flux job wait-event -vt 60 $job_project_A depend
'

# If a user is added to the DB without specifying any projects, a default
# project "*" is added for the user automatically, and jobs submitted without
# specifying a project will fall under "*" - this is the case for the first
# added user in this test file.
#
# Every user who is added to the DB belongs to the "*" project, but will only
# run jobs under "*" if they do not already have another default project.
#
# If a user is added to the DB with a specified project name, any job submitted
# without specifying a project name will fall under that project name - this is
# the case for the second user in this test file.
test_expect_success 'add users to flux-accounting DB and to plugin; jobs transition to RUN' '
	flux account add-user --username=user1 --userid=5001 --bank=account1 &&
	flux account add-user \
		--username=user2 \
		--userid=5002 \
		--bank=account1 \
		--projects=projectA &&
	flux account-priority-update -p ${DB_PATH} &&
	flux job wait-event -vt 60 $job_project_star alloc &&
	flux job wait-event -vt 60 $job_project_A alloc
'

test_expect_success 'check that first submitted job has project "*" listed in eventlog' '
	flux job info $job_project_star eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"\*\"" eventlog.out &&
	flux cancel $job_project_star
'

test_expect_success 'check that second submitted job has project "projectA" listed in eventlog' '
	flux job info $job_project_A eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"projectA\"" eventlog.out &&
	flux cancel $job_project_A
'

test_expect_success 'add a user with a list of projects to the DB' '
	flux account add-user \
		--username=user3 \
		--userid=5003 \
		--bank=account1 \
		--projects="projectA,projectB"
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'successfully submit a job under a valid project' '
	jobid=$(flux python ${SUBMIT_AS} 5003 --setattr=system.project=projectA hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid jobspec > jobspec.out &&
	grep "projectA" jobspec.out &&
	flux cancel $jobid
'

test_expect_success 'submit a job under a project that does not exist' '
	test_must_fail flux python ${SUBMIT_AS} 5003 --setattr=system.project=projectFOO \
		hostname > project_dne.out 2>&1 &&
	test_debug "cat project_dne.out" &&
	grep \
		"project \"projectFOO\" not valid for user;
		 valid projects for user: projectA,projectB,*" project_dne.out
'

test_expect_success 'submit a job under a project that user does not belong to' '
	test_must_fail flux python ${SUBMIT_AS} 5003 --setattr=system.project=projectC \
		hostname > project_invalid.out 2>&1 &&
	test_debug "cat project_invalid.out" &&
	grep \
		"project \"projectC\" not valid for user;
		 valid projects for user: projectA,projectB,*" project_invalid.out
'

test_expect_success 'successfully submit a job under a default project' '
	jobid=$(flux python ${SUBMIT_AS} 5003 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"projectA\"" eventlog.out &&
	flux cancel $jobid
'

test_expect_success 'successfully submit a job under a secondary project' '
	jobid=$(flux python ${SUBMIT_AS} 5003 --setattr=system.project=projectB hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid jobspec > jobspec.out &&
	grep "projectB" jobspec.out &&
	flux cancel $jobid
'

test_expect_success 'update the default project for user and submit job under new default' '
	flux account edit-user user3 --default-project=projectB &&
	flux account-priority-update -p ${DB_PATH} &&
	jobid=$(flux python ${SUBMIT_AS} 5003 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"projectB\"" eventlog.out &&
	flux cancel $jobid
'

test_expect_success 'add a user without specifying any projects (will add a default project of "*")' '
	flux account add-user --username=user4 --userid=5004 --bank=account1 &&
	flux account-priority-update -p ${DB_PATH} &&
	jobid=$(flux python ${SUBMIT_AS} 5004 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"\*\"" eventlog.out &&
	flux cancel $jobid
'

test_expect_success 'add a new default project to the new user and update the plugin' '
	flux account edit-user user4 --projects=projectA --default-project=projectA &&
	flux account-priority-update -p ${DB_PATH} &&
	jobid=$(flux python ${SUBMIT_AS} 5004 hostname) &&
	flux job wait-event -f json $jobid priority &&
	flux job info $jobid eventlog > eventlog.out &&
	grep "\"attributes.system.project\":\"projectA\"" eventlog.out &&
	flux cancel $jobid
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
