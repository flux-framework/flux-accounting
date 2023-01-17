#!/bin/bash

test_description='Test multi-factor priority plugin order with different --urgency values'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py

mkdir -p config

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'disable age factor in multi-factor priority plugin' '
	cat >config/test.toml <<-EOT &&
	[priority_factors]
	age_weight = 0
	EOT
	flux config reload
'

test_expect_success 'create a group of users with the same fairshare value' '
	cat <<-EOF >fake_payload.py
	import flux
	import json

	bulk_user_data = {
		"data" : [
			{"userid": 5011, "bank": "account1", "def_bank": "account1", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5012, "bank": "account1", "def_bank": "account1", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5013, "bank": "account1", "def_bank": "account1", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5021, "bank": "account2", "def_bank": "account2", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5022, "bank": "account2", "def_bank": "account2", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5031, "bank": "account3", "def_bank": "account3", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
			{"userid": 5032, "bank": "account3", "def_bank": "account3", "fairshare": 0.5, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""}
		]
	}
	bulk_queue_data = {
		"data" : [
			{
				"queue": "default",
				"priority": 0,
				"min_nodes_per_job": 0,
				"max_nodes_per_job": 5,
				"max_time_per_job": 64000
			}
		]
	}
	flux.Flux().rpc("job-manager.mf_priority.rec_update", json.dumps(bulk_user_data)).get()
	flux.Flux().rpc("job-manager.mf_priority.rec_q_update", json.dumps(bulk_queue_data)).get()
	EOF
'

test_expect_success 'send the user information to the plugin' '
	flux python fake_payload.py
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'submit jobs as each user with random urgencies' '
	flux python ${SUBMIT_AS} 5011 --urgency=9 hostname &&
	flux python ${SUBMIT_AS} 5012 --urgency=4 hostname &&
	flux python ${SUBMIT_AS} 5013 --urgency=1 hostname &&
	flux python ${SUBMIT_AS} 5021 --urgency=6 hostname &&
	flux python ${SUBMIT_AS} 5022 --urgency=5 hostname &&
	flux python ${SUBMIT_AS} 5031 --urgency=7 hostname &&
	flux python ${SUBMIT_AS} 5032 --urgency=2 hostname
'

test_expect_success 'check order of job queue' '
	flux jobs -A --suppress-header --format={userid} > small_no_tie.test &&
	cat <<-EOF >small_no_tie.expected &&
	5011
	5031
	5021
	5022
	5012
	5032
	5013
	EOF
	test_cmp small_no_tie.expected small_no_tie.test
'

test_done
