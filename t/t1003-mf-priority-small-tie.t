#!/bin/bash

test_description='Test multi-factor priority plugin with some ties'

. `dirname $0`/sharness.sh
MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
SEND_PAYLOAD=${SHARNESS_TEST_SRCDIR}/scripts/send_payload.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job

flux setattr log-stderr-level 1

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

test_expect_success 'create a group of users with some ties in fairshare values' '
	cat <<-EOF >fake_small_tie.json
	{
		"data" : [
			{"userid": 5011, "bank": "account1", "def_bank": "account1", "fairshare": 0.5, "max_jobs": 5},
			{"userid": 5012, "bank": "account1", "def_bank": "account1", "fairshare": 0.5, "max_jobs": 5},
			{"userid": 5013, "bank": "account1", "def_bank": "account1", "fairshare": 0.75, "max_jobs": 5},
			{"userid": 5021, "bank": "account2", "def_bank": "account2", "fairshare": 0.5, "max_jobs": 5},
			{"userid": 5022, "bank": "account2", "def_bank": "account2", "fairshare": 0.5, "max_jobs": 5},
			{"userid": 5023, "bank": "account2", "def_bank": "account2", "fairshare": 0.75, "max_jobs": 5},
			{"userid": 5031, "bank": "account3", "def_bank": "account3", "fairshare": 1.0, "max_jobs": 5},
			{"userid": 5032, "bank": "account3", "def_bank": "account3", "fairshare": 0.875, "max_jobs": 5}
		]
	}
	EOF
'

test_expect_success 'send the user information to the plugin' '
	flux python ${SEND_PAYLOAD} fake_small_tie.json
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
	flux python ${SUBMIT_AS} 5032 hostname
'

test_expect_success 'check order of job queue' '
	flux jobs -A --suppress-header --format={userid} > small_tie.test &&
	cat <<-EOF >small_tie.expected &&
	5031
	5032
	5013
	5023
	5011
	5012
	5021
	5022
	EOF
	test_cmp small_tie.expected small_tie.test
'

test_done
