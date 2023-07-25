#!/bin/bash

test_description='Test multi-factor priority plugin order with different --urgency values'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py
SAME_FAIRSHARE=${SHARNESS_TEST_SRCDIR}/expected/sample_payloads/same_fairshare.json

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
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

test_expect_success 'send the user information to the plugin' '
	flux python ${SEND_PAYLOAD} ${SAME_FAIRSHARE}
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
