#!/bin/bash

test_description='reload priority plugin while a job is in CLEANUP'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db
EPILOG_RELEASE=$(pwd)/epilog.release

test_under_flux 1 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

check_run_usage() {
	expected=$1

	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == ${expected}" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == ${expected}" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_cores == ${expected}" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_run_jobs == ${expected}" \
		<query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_nodes == ${expected}" \
		<query.json
}

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'add queue to DB' '
	flux account add-queue pdebug
'

test_expect_success 'add banks to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add association to DB' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--queues=pdebug \
		--max-nodes=100 \
		--max-cores=100 \
		--max-active-jobs=1000 \
		--max-running-jobs=1000
'

test_expect_success 'configure queue and delayed epilog' '
	cat >config/test.toml <<-EOT &&
	[exec.testexec]
	allow-guests = true

	[queues.pdebug]

	[job-manager.epilog]
	command = [ "sh", "-c",
	            "while test ! -f ${EPILOG_RELEASE}; do sleep 0.1; done" ]
	timeout = "30s"
	EOT
	flux config reload &&
	flux queue start --all &&
	flux jobtap load perilog.so
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'job enters CLEANUP with run usage counted' '
	job=$(flux python ${SUBMIT_AS} 50001 \
		--setattr=system.exec.test.run_duration=0.1s \
		-N1 -n1 --queue=pdebug true) &&
	flux job wait-event -t 5 ${job} alloc &&
	flux job wait-event -t 5 ${job} finish &&
	flux job wait-event -t 5 \
		--match-context=description="job-manager.epilog" \
		${job} epilog-start &&
	check_run_usage 1
'

test_expect_success 'reload priority plugin while job is in CLEANUP' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} \
		"config=$(flux account export-json)"
'

test_expect_success 'CLEANUP job run usage is restored after reload' '
	check_run_usage 1
'

test_expect_success 'run usage is zero after CLEANUP job becomes inactive' '
	touch ${EPILOG_RELEASE} &&
	flux job wait-event -t 30 ${job} clean &&
	check_run_usage 0
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
