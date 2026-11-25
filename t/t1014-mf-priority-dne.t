#!/bin/bash

test_description='Test DNE job accounting with a late user/bank info load'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'submit a number of jobs with no user/bank info loaded to plugin' '
	jobid1=$(flux submit --wait-event=depend hostname) &&
	jobid2=$(flux submit --wait-event=depend hostname) &&
	jobid3=$(flux submit --wait-event=depend hostname)
'

test_expect_success 'make sure jobs get held in state PRIORITY' '
	flux job wait-event -vt 60 ${jobid1} depend &&
	flux job wait-event -vt 60 ${jobid2} depend &&
	flux job wait-event -vt 60 ${jobid3} depend
'

test_expect_success 'cancel held jobs' '
	flux cancel ${jobid1} &&
	flux cancel ${jobid2} &&
	flux cancel ${jobid3}
'

test_expect_success 'submit job #1 with no user/bank info loaded to plugin' '
	jobid1=$(flux submit --wait-event=depend hostname)
'

test_expect_success 'check that job #1 is in state PRIORITY' '
	flux job wait-event -vt 60 ${jobid1} depend
'

test_expect_success 'send the user/bank information to the plugin without reprioritizing all active jobs' '
	cat <<-EOF >fake_payload.py
	import flux
	import pwd
	import getpass
	import json

	username = getpass.getuser()
	userid = pwd.getpwnam(username).pw_uid
	# create an array of JSON payloads
	bulk_update_data = {
		"data" : [
			{
				"userid": userid,
				"bank": "account3",
				"def_bank": "account3",
				"fairshare": 0.45321,
				"max_running_jobs": 10,
				"max_active_jobs": 12,
				"max_nodes": 2147483647,
				"max_cores": 2147483647,
				"queues": "standby,special",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_sched_jobs": 2147483647
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(bulk_update_data)).get()
	bulk_queue_data = {
		"data" : [
			{
				"queue": "default",
				"priority": 0,
				"max_running_jobs": 2147483647,
				"max_sched_jobs": 2147483647,
				"max_sched_nodes_per_assoc": 2147483647,
				"max_sched_cores_per_assoc": 2147483647
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_q_update", json.dumps(bulk_queue_data)).get()
	EOF
	flux python fake_payload.py
'

test_expect_success 'submit job #2 which should run before job #1' '
	jobid2=$(flux submit hostname) &&
	flux job wait-event -t 15 ${jobid2} clean
'

test_expect_success 'cancel job #1' '
	flux cancel ${jobid1}
'

# Explicit missing banks cause repeated placeholder initialization for one
# user. The placeholder keeps each job's active charge, but even a queue limit
# that would hold them does not hold jobs attached to it in DEPEND, since the
# placeholder combines usage from all of a user's banks.
test_expect_success 'reload with a queue limit and no association data' '
	flux job wait-event -t 15 ${jobid1} clean &&
	userid=$(id -u) &&
	cat >queue-limit.json <<-EOF &&
	{"queues": [{
		"queue": "",
		"priority": 0,
		"max_running_jobs": 0,
		"max_sched_jobs": 2147483647,
		"max_sched_nodes_per_assoc": 2147483647,
		"max_sched_cores_per_assoc": 2147483647
	}]}
	EOF
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-limit.json)"
'

test_expect_success 'first missing bank creates a charged DNE job that is not held' '
	dne1=$(flux submit --bank=A --setattr=project=* sleep inf) &&
	flux job wait-event -t 15 ${dne1} depend &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1 and (.held_jobs | length) == 0" query.json
'

test_expect_success 'another missing bank preserves the existing DNE charge' '
	dne2=$(flux submit --bank=B --setattr=project=* sleep inf) &&
	flux job wait-event -t 15 ${dne2} depend &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 2 and (.held_jobs | length) == 0" query.json
'

test_expect_success 'cancelling the first job preserves the second charge' '
	flux cancel ${dne1} &&
	flux job wait-event -t 15 ${dne1} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1" query.json
'

test_expect_success 'cancelling the second job clears DNE usage' '
	flux cancel ${dne2} &&
	flux job wait-event -t 15 ${dne2} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0 and (.held_jobs | length) == 0" query.json
'

# an association whose real max_running_jobs happens to be 999 must not be
# mistaken for the DNE placeholder when its job reaches job.state.priority
test_expect_success 'reload with an unrestricted queue and no association data' '
	cat >queue-unlimited.json <<-EOF &&
	{"queues": [{
		"queue": "",
		"priority": 0,
		"max_running_jobs": 2147483647,
		"max_sched_jobs": 2147483647,
		"max_sched_nodes_per_assoc": 2147483647,
		"max_sched_cores_per_assoc": 2147483647
	}]}
	EOF
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)"
'

test_expect_success 'load an association with max_running_jobs of 999' '
	cat <<-EOF >payload.py &&
	import flux
	import json
	import sys

	data = {
		"data": [
			{
				"userid": $(id -u),
				"bank": "test_bank",
				"def_bank": "test_bank",
				"fairshare": 0.5,
				"max_running_jobs": 999,
				"max_active_jobs": 1000,
				"max_nodes": 2147483647,
				"max_cores": 2147483647,
				"queues": sys.argv[1] if len(sys.argv) > 1 else "",
				"active": 1,
				"projects": "*",
				"def_project": "*",
				"max_sched_jobs": 2147483647
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(data)).get()
	EOF
	flux python payload.py
'

test_expect_success 'job under the 999-limit association is not treated as DNE' '
	job999=$(flux submit --bank=test_bank sleep inf) &&
	flux job wait-event -t 15 ${job999} alloc &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_run_jobs == 1" query.json
'

test_expect_success 'cancel job under the 999-limit association' '
	flux cancel ${job999} &&
	flux job wait-event -t 15 ${job999} clean
'

# a job charged to the DNE placeholder must be uncharged from it once the job
# moves to its real association
test_expect_success 'reload the plugin with no association data' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)"
'

test_expect_success 'a job submitted with no association data charges DNE' '
	jobdne=$(flux submit --wait-event=depend sleep inf) &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1" query.json
'

test_expect_success 'load association data and reprioritize the job' '
	flux python payload.py &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	flux job wait-event -t 15 ${jobdne} alloc
'

test_expect_success 'DNE is uncharged and the real association is charged' '
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_run_jobs == 1" query.json
'

test_expect_success 'cancel the formerly DNE job' '
	flux cancel ${jobdne} &&
	flux job wait-event -t 15 ${jobdne} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 0 and .cur_run_jobs == 0" query.json
'

# a job re-seen after a plugin reload must be charged to DNE just like a
# newly submitted job, then move its charge when association data arrives
test_expect_success 'submit a job with no association data' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)" &&
	jobreload=$(flux submit --wait-event=depend sleep inf) &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1" query.json
'

test_expect_success 'a job re-seen after a reload charges DNE' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)" &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1" query.json
'

test_expect_success 'load association data and reprioritize the re-seen job' '
	flux python payload.py &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	flux job wait-event -t 15 ${jobreload} alloc
'

test_expect_success 'the re-seen job moves its active charge off DNE' '
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_run_jobs == 1" query.json
'

test_expect_success 'cancel the re-seen job' '
	flux cancel ${jobreload} &&
	flux job wait-event -t 15 ${jobreload} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 0 and .cur_run_jobs == 0" query.json
'

# job & resource counts are correctly reconciled to the correct association
# after a flux-accounting update and before the job begins running
test_expect_success 'submit a job that stays in SCHED' '
	flux python payload.py &&
	flux queue stop &&
	jobsched=$(flux submit --bank=test_bank sleep inf) &&
	flux job wait-event -t 15 ${jobsched} priority &&
	test "$(flux jobs -no {state} ${jobsched})" = SCHED
'

test_expect_success 'a replayed SCHED job charges DNE jobs and resources' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)" &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1 and .cur_sched_jobs == 1 and
		.queue_usage[\"\"].cur_sched_jobs == 1 and
		.queue_usage[\"\"].cur_sched_nodes == 1 and
		.queue_usage[\"\"].cur_sched_cores == 1" query.json
'

test_expect_success 'reprioritizing moves SCHED jobs and resources to the real bank' '
	flux python payload.py &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0 and .cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 0 and
		.queue_usage[\"\"].cur_sched_cores == 0" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_sched_jobs == 1 and
		.queue_usage[\"\"].cur_sched_jobs == 1 and
		.queue_usage[\"\"].cur_sched_nodes == 1 and
		.queue_usage[\"\"].cur_sched_cores == 1" query.json
'

test_expect_success 'the replayed SCHED job runs under its real bank' '
	flux queue start &&
	flux job wait-event -t 15 ${jobsched} alloc &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 1 and .cur_nodes == 1 and .cur_cores == 1 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 1 and
		.queue_usage[\"\"].cur_sched_cores == 1" query.json
'

test_expect_success 'cancelling the replayed SCHED job clears all real-bank usage' '
	flux cancel ${jobsched} &&
	flux job wait-event -t 15 ${jobsched} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 0 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 0 and .cur_nodes == 0 and .cur_cores == 0 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 0 and
		.queue_usage[\"\"].cur_sched_cores == 0" query.json
'

# a job already running when the plugin is reloaded with no flux-accounting
# data is charged to DNE and stays there until it finishes
test_expect_success 'a replayed RUN job charges DNE jobs and resources' '
	jobrun=$(flux submit --bank=test_bank sleep inf) &&
	flux job wait-event -t 15 ${jobrun} alloc &&
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)" &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 1 and .cur_nodes == 1 and .cur_cores == 1 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 1 and
		.queue_usage[\"\"].cur_sched_cores == 1" query.json
'

test_expect_success 'cancelling the replayed RUN job clears DNE without missing job info' '
	flux cancel ${jobrun} &&
	flux job wait-event -t 15 ${jobrun} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 0 and .cur_nodes == 0 and .cur_cores == 0 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 0 and
		.queue_usage[\"\"].cur_sched_cores == 0" query.json &&
	flux job eventlog -f json ${jobrun} >eventlog.json &&
	jq -se "[.[] | select(.name == \"exception\") | .context.type]
		== [\"cancel\"]" eventlog.json
'

# a job in SCHED when the plugin is reloaded with no flux-accounting data can
# be allocated resources before that data arrives; it must run under DNE
# instead of being killed with "job info missing" in job.state.run
test_expect_success 'reload with no association data while a job is in SCHED' '
	flux python payload.py &&
	flux queue stop &&
	joballoc=$(flux submit --bank=test_bank sleep inf) &&
	flux job wait-event -t 15 ${joballoc} priority &&
	test "$(flux jobs -no {state} ${joballoc})" = SCHED &&
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-unlimited.json)"
'

test_expect_success 'the replayed SCHED job starts under DNE before data arrives' '
	flux queue start &&
	flux job wait-event -t 15 ${joballoc} start &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 1 and .cur_nodes == 1 and .cur_cores == 1 and
		.queue_usage[\"\"].cur_sched_jobs == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 1 and
		.queue_usage[\"\"].cur_sched_cores == 1" query.json
'

test_expect_success 'the job keeps running on DNE after association data arrives' '
	flux python payload.py &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	test "$(flux jobs -no {state} ${joballoc})" = RUN &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1 and .cur_run_jobs == 1" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 0 and .cur_run_jobs == 0" query.json
'

test_expect_success 'cancelling the job clears DNE with only a cancel exception' '
	flux cancel ${joballoc} &&
	flux job wait-event -t 15 ${joballoc} clean &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0 and .cur_sched_jobs == 0 and
		.cur_run_jobs == 0 and .cur_nodes == 0 and .cur_cores == 0 and
		.queue_usage[\"\"].cur_sched_nodes == 0 and
		.queue_usage[\"\"].cur_sched_cores == 0" query.json &&
	flux job eventlog -f json ${joballoc} >eventlog.json &&
	jq -se "[.[] | select(.name == \"exception\") | .context.type]
		== [\"cancel\"]" eventlog.json
'

# if a queue is specified on a job held under the special "DNE" bank, it needs
# to be re-validated once the plugin is loaded with valid flux-accounting data
test_expect_success 'configure standby and default queues without association data' '
	flux config load <<-EOF &&
	[queues.default]
	[queues.standby]
	EOF
	jq ".queues[0].queue = \"standby\"" queue-unlimited.json >queue-standby.json &&
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-standby.json)" &&
	flux queue start --all
'

test_expect_success 'accept a configured queue job while association data is missing' '
	jobqueue=$(flux submit --queue=standby --bank=test_bank \
		--wait-event=depend sleep inf) &&
	test "$(flux jobs -no {state} ${jobqueue})" = PRIORITY &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 1" query.json
'

test_expect_success 'the configured queue job runs when its real bank permits standby' '
	flux python payload.py standby &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	flux job wait-event -t 15 ${jobqueue} alloc &&
	flux job info ${jobqueue} eventlog >eventlog.out &&
	grep "\"attributes.system.project\":\"\*\"" eventlog.out &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"DNE\") |
		.cur_active_jobs == 0" query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks[] | select(.bank_name == \"test_bank\") |
		.cur_active_jobs == 1 and .cur_run_jobs == 1 and
		.queue_usage.standby.cur_run_jobs == 1" query.json &&
	flux cancel ${jobqueue} &&
	flux job wait-event -t 15 ${jobqueue} clean
'

test_expect_success 'submit another configured queue job before association data arrives' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load ${MULTI_FACTOR_PRIORITY} "config=$(cat queue-standby.json)" &&
	jobinvalid=$(flux submit --queue=standby --bank=test_bank \
		--wait-event=depend sleep inf) &&
	test "$(flux jobs -no {state} ${jobinvalid})" = PRIORITY
'

test_expect_success 'a real bank without standby raises an invalid queue exception' '
	flux python payload.py &&
	flux python -c "import flux; flux.Flux().rpc(\"job-manager.mf_priority.reprioritize\").get()" &&
	flux job wait-event -t 15 ${jobinvalid} clean &&
	flux job eventlog -f json ${jobinvalid} >eventlog.json &&
	jq -se "[.[] | select(.name == \"exception\") | .context] |
		length == 1 and .[0].type == \"mf_priority\" and
		.[0].severity == 0 and
		.[0].note == \"queue \\\"standby\\\" not valid for user; valid queues for user: \"" \
		eventlog.json &&
	flux jobtap query mf_priority.so >query.json &&
	jq -e ".mf_priority_map[] | select(.userid == ${userid}) |
		.banks | all(.[]; .cur_active_jobs == 0 and .cur_run_jobs == 0)" \
		query.json
'

test_expect_success 'remove queue configuration' '
	flux config load </dev/null &&
	test_must_fail flux config get queues
'

test_done
