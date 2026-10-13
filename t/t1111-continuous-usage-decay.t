#!/bin/bash

test_description='test continuous usage decay with completed jobs'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

test_under_flux 1 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'create continuous-decay flux-accounting DB' '
	flux account -p ${DB} create-db --decay-method=continuous
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'continuous decay mode is configured' '
	flux account list-configs -o "{key}->{value}" > configs.out &&
	grep "decay_method->continuous" configs.out
'

test_expect_success 'add banks and association' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=50001 --bank=A
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit and complete job under bank A' '
	job=$(flux python ${SUBMIT_AS} 50001 --bank=A -N1 sleep inf) &&
	flux job wait-event -t 5 ${job} alloc &&
	sleep 1 &&
	flux cancel ${job} &&
	flux job wait-event -t 5 ${job} clean
'

test_expect_success 'continuous update charges completed job' '
	flux account-fetch-job-records -p ${DB} &&
	flux account-update-usage -p ${DB} &&
	flux account view-user user1 > user1.json &&
	test_debug "jq -S . <user1.json" &&
	jq -e ".[0] | .job_usage > 0" <user1.json
'

test_expect_success 'second continuous update does not recharge job' '
	before=$(jq -r ".[0].job_usage" <user1.json) &&
	flux account-update-usage -p ${DB} &&
	flux account view-user user1 > user1-second.json &&
	after=$(jq -r ".[0].job_usage" <user1-second.json) &&
	jq -e -n --argjson before "${before}" --argjson after "${after}" \
		"\$after <= \$before and \$after > 0"
'

test_expect_success 'continuous mode rejects detailed job-usage breakdown' '
	test_must_fail flux account view-user -J user1 > nobreakdown.err 2>&1 &&
	grep "view-user: ValueError: detailed job usage breakdowns are unavailable in continuous mode" \
		nobreakdown.err
'

test_expect_success 'reset period edit preserves continuous usage' '
	before=$(jq -r ".[0].job_usage" <user1-second.json) &&
	flux account edit-config priority_usage_reset_period=14d &&
	flux account view-user user1 > user1-reset-period.json &&
	after=$(jq -r ".[0].job_usage" <user1-reset-period.json) &&
	jq -e -n --argjson before "${before}" --argjson after "${after}" \
		"\$after == \$before"
'

test_expect_success 'switching back to periodic resets usage and enables breakdown' '
	flux account edit-config decay_method=periodic &&
	flux account view-user user1 > user1-periodic.json &&
	jq -e ".[0] | .job_usage == 0.0" <user1-periodic.json &&
	flux account view-user -J user1
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
