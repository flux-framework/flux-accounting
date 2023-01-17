#!/bin/bash

test_description='Test multi-factor priority plugin with many ties'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py

mkdir -p config

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
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

test_expect_success 'create a group of users with many ties in fairshare values' '
	cat <<-EOF >fake_small_tie_all.json
	{
	    "data" : [
	        {"userid": 5011, "bank": "account1", "def_bank": "account1", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5012, "bank": "account1", "def_bank": "account1", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5013, "bank": "account1", "def_bank": "account1", "fairshare": 1, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5021, "bank": "account2", "def_bank": "account2", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5022, "bank": "account2", "def_bank": "account2", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5023, "bank": "account2", "def_bank": "account2", "fairshare": 1, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5031, "bank": "account3", "def_bank": "account3", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5032, "bank": "account3", "def_bank": "account3", "fairshare": 0.666667, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""},
	        {"userid": 5033, "bank": "account3", "def_bank": "account3", "fairshare": 1, "max_running_jobs": 5, "max_active_jobs": 7, "queues": ""}
	    ]
	}
	EOF
'

test_expect_success 'send the user information to the plugin' '
	flux python ${SEND_PAYLOAD} fake_small_tie_all.json
'

test_expect_success 'add a default queue and send it to the plugin' '
	cat <<-EOF >fake_payload.py
	import flux
	import json

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
	flux.Flux().rpc("job-manager.mf_priority.rec_q_update", json.dumps(bulk_queue_data)).get()
	EOF
	flux python fake_payload.py
'

test_expect_success 'stop the queue' '
	flux queue stop
'

test_expect_success 'submit jobs as each user' '
	flux python ${SUBMIT_AS} 5011 hostname &&
	flux python ${SUBMIT_AS} 5012 hostname &&
	flux python ${SUBMIT_AS} 5013 hostname &&
	flux python ${SUBMIT_AS} 5021 hostname &&
	flux python ${SUBMIT_AS} 5022 hostname &&
	flux python ${SUBMIT_AS} 5023 hostname &&
	flux python ${SUBMIT_AS} 5031 hostname &&
	flux python ${SUBMIT_AS} 5032 hostname &&
	flux python ${SUBMIT_AS} 5033 hostname
'

test_expect_success 'check order of job queue' '
	flux jobs -A --suppress-header --format={userid} > small_tie_all.test &&
	cat <<-EOF >small_tie_all.expected &&
	5013
	5023
	5033
	5011
	5012
	5021
	5022
	5031
	5032
	EOF
	test_cmp small_tie_all.expected small_tie_all.test
'

test_done
