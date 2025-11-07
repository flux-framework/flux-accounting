#!/bin/bash

test_description='test initializing priority plugin with DB information on load'

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

test_expect_success 'add a queue to the DB' '
	flux account add-queue pdebug
'

test_expect_success 'add associations' '
	flux account add-user --username=user1 --bank=A --userid=50001 --queues=pdebug
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

# Loading the priority plugin with no key-value pairs does *not* initialize it
# with any flux-accounting DB information, and therefore requires the
# "account-priority-update" command to be run to send DB information to the
# plugin to be unpacked.
test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY} &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'send flux-accounting database information to plugin' '
	flux account-priority-update -p ${DB}
'

test_expect_success 'submit a job' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N 1 -n 1 --queue=pdebug sleep inf) &&
	flux job wait-event -t 3 ${job1} alloc
'

# Ensure the association has an active and running job
test_expect_success 'association has 1 active, running job' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 1" <query.json
'


# When the plugin is reloaded, all aux items set by the priority plugin are
# removed, and thus, we lose tracking of associations' jobs. Initializing the
# priority plugin with the DB information will allow active jobs that pass
# through job.new to be accurately associated with each Association.
test_expect_success 'reload multi-factor priority plugin with DB initialization' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)"
'

# Now, the running job submitted earlier is correctly associated with the
# association without requiring a separate update via
# "flux account-priority-update".
test_expect_success 'association has accurate job, resource counts' '
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
		 .banks[0].cur_nodes == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_cores == 1" <query.json
'

test_expect_success 'association has accurate job, resource counts in queue' '
   jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_run_jobs == 1" <query.json &&
   jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_nodes == 1" <query.json
'

test_expect_success 'cancel job' '
	flux cancel ${job1} &&
	flux job wait-event -t 10 ${job1} clean
'

test_expect_success 'association has accurate job, resource counts after cleanup' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_active_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_nodes == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_cores == 0" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_run_jobs == 0" <query.json &&
   jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].queue_usage[\"pdebug\"].cur_nodes == 0" <query.json
'

test_expect_success 'queue_table is properly unpacked in plugin' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".queues.pdebug.name == \"pdebug\"" <query.json &&
	jq -e ".queues.pdebug.priority == 0" <query.json
'

test_expect_success 'add a project to the DB' '
	flux account add-project project1
'

test_expect_success 'reload plugin with config' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'project_table is properly unpacked in plugin' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".projects | length == 2" <query.json &&
	jq -e ".projects[0] == \"*\"" <query.json &&
	jq -e ".projects[1] == \"project1\"" <query.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done