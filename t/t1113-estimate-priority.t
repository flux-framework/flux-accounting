#!/bin/bash

test_description='test estimating priority from the multi-factor priority plugin'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB} -t
'

test_expect_success 'estimate fails before priority plugin is loaded' '
	test_must_fail flux account estimate-priority >unloaded.out 2>&1
'

test_expect_success 'load priority plugin without accounting data' '
	flux jobtap load ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'estimate reports unavailable accounting data' '
	test_must_fail flux account estimate-priority >uninitialized.out 2>&1 &&
	grep "has not been loaded" uninitialized.out
'

# a job submitted before any flux-accounting data is loaded causes the plugin
# to create a "DNE" placeholder association for the submitting user
test_expect_success 'submit a job before accounting data is loaded' '
	jobid_dne=$(flux submit -n1 hostname) &&
	flux job wait-event -vt 60 ${jobid_dne} depend
'

test_expect_success 'estimate --help works' '
	flux account estimate-priority --help
'

test_expect_success 'initialize DB with accounting data' '
	flux account add-queue pdebug --priority=0 &&
	flux account add-queue pbatch --priority=7 &&
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 --priority=1 &&
	flux account add-bank --parent-bank=root B 1 --priority=2 &&
	flux account add-bank --parent-bank=root C 1 --priority=3 &&
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user \
		--username=${username} \
		--bank=A \
		--userid=${uid} \
		--queues=pdebug,pbatch &&
	flux account add-user \
		--username=${username} \
		--bank=B \
		--userid=${uid} \
		--queues=pdebug &&
	flux account add-user \
		--username=${username} \
		--bank=C \
		--userid=${uid} \
		--queues=pdebug,pbatch &&
	flux account edit-factor --factor=fairshare --weight=100 &&
	flux account edit-factor --factor=queue --weight=10 &&
	flux account edit-factor --factor=bank --weight=1000 &&
	flux account edit-factor --factor=urgency --weight=100
'

test_expect_success 'update priority plugin with accounting data' '
	flux account-priority-update -p ${DB}
'

test_expect_success 'job submitted before accounting data was loaded runs' '
	flux job wait-event -vt 60 ${jobid_dne} clean
'

test_expect_success '--all-banks does not report the DNE placeholder' '
	flux account estimate-priority --all-banks --json >no_dne.json &&
	jq -e "all(.[]; .bank != \"DNE\")" no_dne.json
'

# flux account-priority-update also creates a payload for the instance owner,
# which is the test user here; the estimator correctly reports it
test_expect_success 'priority-update adds the instance owner association' '
	jq -e --arg owner "${username}" \
		"map(.bank) == [\"A\", \"B\", \"C\", \$owner]" no_dne.json
'

# reload the plugin with only the DB contents so that the remaining tests see
# the DB-defined default bank, and so that factor weights given in the config
# at load time are exercised
test_expect_success 'reload priority plugin with accounting data' '
	flux jobtap remove mf_priority.so &&
	flux jobtap load \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)"
'

test_expect_success 'configure Flux queues' '
	cat >config/queues.toml <<-EOF &&
	[policy.jobspec.defaults.system]
	queue = "pdebug"

	[queues.pdebug]
	[queues.pbatch]
	[queues.unknown]
	EOF
	flux config reload &&
	flux queue start --all
'

test_expect_success 'default bank estimate works' '
	flux account estimate-priority --json >estimate_default.json &&
	jq -e \
		".[0].bank == \"A\" and .[0].queue == \"pdebug\" and
		 .[0].urgency == 16 and .[0].priority == 1050 and
		 .[0].error == null" \
		estimate_default.json &&
	job_default=$(flux submit -n1 hostname) &&
	flux job wait-event -f json ${job_default} priority |
		jq ".context.priority" >actual_default &&
	jq ".[0].priority" estimate_default.json >estimated_default &&
	test_cmp estimated_default actual_default
'

test_expect_success 'explicit bank and queue estimate matches submitted job' '
	flux account estimate-priority \
		--bank=A --queue=pbatch --json >estimate_pbatch.json &&
	jq -e ".[0].priority == 1120" estimate_pbatch.json &&
	job_pbatch=$(flux submit \
		--setattr=system.bank=A \
		--queue=pbatch \
		-n1 hostname) &&
	flux job wait-event -f json ${job_pbatch} priority |
		jq ".context.priority" >actual_pbatch &&
	jq ".[0].priority" estimate_pbatch.json >estimated_pbatch &&
	test_cmp estimated_pbatch actual_pbatch
'

test_expect_success 'custom owner urgency is included in estimate' '
	flux account estimate-priority \
		--bank=A --queue=pbatch --urgency=20 --json >estimate_u20.json &&
	jq -e ".[0].priority == 1520" estimate_u20.json &&
	job_u20=$(flux submit \
		--setattr=system.bank=A \
		--queue=pbatch \
		--urgency=20 \
		-n1 hostname) &&
	flux job wait-event -f json ${job_u20} priority |
		jq ".context.priority" >actual_u20 &&
	jq ".[0].priority" estimate_u20.json >estimated_u20 &&
	test_cmp estimated_u20 actual_u20
'

test_expect_success 'hold urgency returns minimum priority' '
	flux account estimate-priority \
		--bank=A --urgency=0 --json >estimate_hold.json &&
	jq -e ".[0].priority == 0 and .[0].error == null" estimate_hold.json
'

test_expect_success 'default output includes fixed estimator columns' '
	flux account estimate-priority --bank=A >estimate_table.out &&
	grep "BANK.*QUEUE.*URGENCY.*PRIORITY.*ERROR" estimate_table.out
'

test_expect_success '--all-banks is bank ordered with partial queue errors' '
	flux account estimate-priority \
		--all-banks --queue=pbatch --json >all_banks.json &&
	jq -e "map(.bank) == [\"A\", \"B\", \"C\"]" all_banks.json &&
	jq -e \
		".[0].priority == 1120 and .[0].error == null and
		 .[1].priority == null and (.[1].error | test(\"queue\")) and
		 .[2].priority == 3120 and .[2].error == null" \
		all_banks.json
'

test_expect_success 'partial --all-banks success exits successfully' '
	flux account estimate-priority --all-banks --queue=pbatch >partial.out
'

test_expect_success 'disabled associations appear as error rows' '
	flux account delete-user ${username} C &&
	flux account-priority-update -p ${DB} &&
	flux account estimate-priority --all-banks --json >disabled.json &&
	jq -e \
		".[] | select(.bank == \"C\") |
		 .priority == null and (.error | test(\"disabled\"))" \
		disabled.json
'

test_expect_success 'estimation does not mutate plugin state' '
	flux jobtap query mf_priority.so | jq -S . >query_before.json &&
	flux account estimate-priority --all-banks --queue=pbatch >readonly.out &&
	flux account estimate-priority --bank=A --json >readonly.json &&
	flux jobtap query mf_priority.so | jq -S . >query_after.json &&
	test_cmp query_before.json query_after.json
'

test_expect_success 'unknown queues are allowed when deny_unknown_queues is false' '
	flux account estimate-priority \
		--bank=A --queue=unknown --json >unknown_allowed.json &&
	jq -e ".[0].priority == 1050 and .[0].error == null" \
		unknown_allowed.json
'

test_expect_success 'unknown queues become row errors when deny_unknown_queues is true' '
	flux account edit-config deny_unknown_queues=true &&
	flux account-priority-update -p ${DB} &&
	test_must_fail flux account estimate-priority \
		--bank=A --queue=unknown --json >unknown_denied.json &&
	jq -e ".[0].priority == null and (.[0].error | test(\"unknown\"))" \
		unknown_denied.json
'

test_expect_success 'non-owner user can estimate their own priority' '
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$(id -u) &&
		flux account estimate-priority \
			--bank=A --queue=pbatch --json >guest_ok.json
	) &&
	jq -e ".[0].priority == 1120 and .[0].error == null" guest_ok.json
'

test_expect_success 'non-owner urgency above default is rejected' '
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=$(id -u) &&
		test_must_fail flux account estimate-priority \
			--bank=A --urgency=20 >guest_urgency.out 2>&1 &&
		grep "requires instance owner credentials" guest_urgency.out
	)
'

test_expect_success 'unknown caller exits nonzero with a useful message' '
	( export FLUX_HANDLE_ROLEMASK=0x2 &&
	  export FLUX_HANDLE_USERID=59999 &&
		test_must_fail flux account estimate-priority \
			>unknown_user.out 2>&1 &&
		grep "cannot find user/bank" unknown_user.out
	)
'

test_expect_success 'estimate under a bank the caller does not belong to fails' '
	test_must_fail flux account estimate-priority \
		--bank=root >wrong_bank.out 2>&1 &&
	grep "cannot find user/bank" wrong_bank.out
'

test_expect_success 'malformed RPC selections fail' '
	test_must_fail flux python -c \
		"import flux; flux.Flux().rpc(\"job-manager.mf_priority.estimate\", {\"bank\":\"A\", \"all_banks\":True}).get()" &&
	test_must_fail flux python -c \
		"import flux; flux.Flux().rpc(\"job-manager.mf_priority.estimate\", {\"urgency\":32}).get()"
'

test_expect_success 'mistyped RPC fields are rejected' '
	test_must_fail flux python -c \
		"import flux; flux.Flux().rpc(\"job-manager.mf_priority.estimate\", {\"all_banks\":1}).get()" &&
	test_must_fail flux python -c \
		"import flux; flux.Flux().rpc(\"job-manager.mf_priority.estimate\", {\"urgency\":\"20\"}).get()"
'

test_expect_success 'cleared default queue falls back to no queue factor' '
	cat >config/queues.toml <<-EOF &&
	[queues.pdebug]
	[queues.pbatch]
	[queues.unknown]
	EOF
	flux config reload &&
	flux account estimate-priority --bank=A --json >no_default_queue.json &&
	jq -e \
		".[0].bank == \"A\" and .[0].queue == null and
		 .[0].urgency == 16 and .[0].priority == 1050 and
		 .[0].error == null" \
		no_default_queue.json
'

test_expect_success 'empty queue config falls back to no queue factor' '
	: >config/queues.toml &&
	flux config reload &&
	flux account estimate-priority --bank=A --json >empty_queue_config.json &&
	jq -e \
		".[0].bank == \"A\" and .[0].queue == null and
		 .[0].urgency == 16 and .[0].priority == 1050 and
		 .[0].error == null" \
		empty_queue_config.json
'

test_expect_success 'all-error output exits nonzero' '
	flux account delete-user ${username} A &&
	flux account delete-user ${username} B &&
	flux account-priority-update -p ${DB} &&
	test_must_fail flux account estimate-priority \
		--all-banks --queue=pbatch --json \
		>all_error.json &&
	jq -e "all(.[]; .priority == null and .error != null)" all_error.json
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
