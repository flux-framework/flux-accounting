#!/bin/bash

test_description='test clearing and resetting usage for a bank'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

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
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add associations' '
	flux account add-user --username=user1 --bank=A --userid=50001 &&
	flux account add-user --username=user1 --bank=B --userid=50001
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

# The use of 'sleep 1' here is to give both jobs a little time to run so that
# both associations accumulate some job usage
test_expect_success 'submit sleep jobs under both banks' '
	job1=$(flux python ${SUBMIT_AS} 50001 --bank=A -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	job2=$(flux python ${SUBMIT_AS} 50001 --bank=B -N1 sleep inf) &&
	flux job wait-event -t 5 ${job2} alloc &&
	sleep 1
'

test_expect_success 'insert job records into DB and modify runtime' '
	flux cancel ${job1} ${job2} &&
	flux job wait-event -t 5 ${job1} clean &&
	flux job wait-event -t 5 ${job2} clean
'

test_expect_success 'update-usage will update DB after discovering new jobs' '
	flux account-fetch-job-records -p ${DB}
	flux account-update-usage -p ${DB} &&
	flux account-update-fshare -p ${DB}
'

test_expect_success 'clear-usage --help works' '
	flux account clear-usage --help
'

test_expect_success 'clear-usage will reset the usage for a single bank back to 0' '
	flux account clear-usage A &&
	flux account view-bank root --tree &&
	flux account view-bank A > bank_A.json &&
	test_debug "jq -S . <bank_A.json" &&
	jq -e ".[0] | .job_usage == 0.0" <bank_A.json
'

test_expect_success 'clear-usage also clears usage for user(s) under bank A' '
	flux account view-user user1 > user1.json &&
	test_debug "jq -S . <user1.json" &&
	jq -e ".[0] | .job_usage == 0.0" <user1.json &&
	jq -e ".[0] | .fairshare == 0.5" <user1.json
'

test_expect_success 'submit sleep under bank A to repopulate usage' '
	job1=$(flux python ${SUBMIT_AS} 50001 --bank=A -N1 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc &&
	sleep 1 &&
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job1} clean
'

test_expect_success 'update-usage will update DB after discovering new jobs' '
	flux account-fetch-job-records -p ${DB}
	flux account-update-usage -p ${DB} &&
	flux account-update-fshare -p ${DB}
'

test_expect_success 'clear-usage accepts multiple banks' '
	flux account clear-usage A B &&
	flux account view-bank root > bank_root.json &&
	jq -e ".[0] | .job_usage == 0.0" <bank_root.json &&
	flux account view-bank A > bank_A.json &&
	jq -e ".[0] | .job_usage == 0.0" <bank_A.json &&
	flux account view-bank B > bank_B.json &&
	jq -e ".[0] | .job_usage == 0.0" <bank_B.json
'

# Jan 1st, 1990 converted to seconds-since-epoch: 631180800
test_expect_success 'usage can be cleared with a specific ignore_older_than date' '
	flux account clear-usage A --ignore-older-than="Jan 1, 1990 8am" &&
	flux account view-bank A > bank_A.json &&
	jq -e ".[0] | .ignore_older_than == 631180800" <bank_A.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
