#!/bin/bash

test_description='test viewing jobs with different ID formats'

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
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add an association' '
	flux account add-user --username=user1 --userid=50001 --bank=A
'

test_expect_success 'send flux-accounting DB information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

test_expect_success 'submit a job' '
	jobid=$(flux python ${SUBMIT_AS} 50001 hostname) &&
	flux job wait-event -f json ${jobid} priority &&
	flux cancel ${jobid}
'

test_expect_success 'run fetch-job-records script' '
	flux account-fetch-job-records -p ${DB_PATH}
'

test_expect_success 'call view-job-records with bad format raises error' '
	test_must_fail flux account view-job-records --format="{jobid.foo}" > bad_arg.err 2>&1 &&
	grep "ValueError: Unknown format field: jobid.foo" bad_arg.err
'

test_expect_success 'view-job-records by default will display jobID format in f58' '
	flux account view-job-records > jobid_default.out &&
	grep ${jobid} jobid_default.out
'

test_expect_success 'jobID is displayed in f58 by default in custom format' '
	flux account view-job-records \
		--format="{jobid:<20} | {nnodes:<8}" > jobid_custom_format.out &&
	grep ${jobid} jobid_custom_format.out
'

test_expect_success 'jobid.dec can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.dec:<20} | {nnodes:<8}" > jobid_dec_custom_format.out &&
	grep $(flux job id --to=dec ${jobid}) jobid_dec_custom_format.out
'

test_expect_success 'jobid.hex can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.hex:<20} | {nnodes:<8}" > jobid_hex_custom_format.out &&
	grep $(flux job id --to=hex ${jobid}) jobid_hex_custom_format.out
'

test_expect_success 'jobid.dothex can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.dothex:<20} | {nnodes:<8}" > jobid_dothex_custom_format.out &&
	grep $(flux job id --to=dothex ${jobid}) jobid_dothex_custom_format.out
'

test_expect_success 'jobid.kvs can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.kvs:<20} | {nnodes:<8}" > jobid_kvs_custom_format.out &&
	grep $(flux job id --to=kvs ${jobid}) jobid_kvs_custom_format.out
'

test_expect_success 'jobid.words can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.words:<20} | {nnodes:<8}" > jobid_words_custom_format.out &&
	grep $(flux job id --to=words ${jobid}) jobid_words_custom_format.out
'

test_expect_success 'jobid.f58plain can be specified in --format' '
	flux account view-job-records \
		--format="{jobid.f58plain:<20} | {nnodes:<8}" > jobid_f58plain_custom_format.out &&
	grep $(flux job id --to=f58plain ${jobid}) jobid_f58plain_custom_format.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
