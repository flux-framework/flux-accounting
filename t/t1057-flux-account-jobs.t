#!/bin/bash

test_description='test listing job priority breakdowns using flux account jobs'

. `dirname $0`/sharness.sh

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
DB_PATH=$(pwd)/FluxAccountingTest.db

mkdir -p config

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
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'load multi-factor priority plugin' '
	flux jobtap load -r .priority-default ${MULTI_FACTOR_PRIORITY}
'

test_expect_success 'check that mf_priority plugin is loaded' '
	flux jobtap list | grep mf_priority
'

# Configure the banks to have drastically different priorities, where
# bank A has the highest priority and bank C has the lowest.
test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 --priority=100 &&
	flux account add-bank --parent-bank=root B 1 --priority=10 &&
	flux account add-bank --parent-bank=root C 1 --priority=1
'

# Configure the queues in flux-accounting to also have drastically different
# priorities, where gold has the highest priority and bronze has the lowest.
test_expect_success 'add some queues to the DB' '
	flux account add-queue bronze --priority=1 &&
	flux account add-queue silver --priority=100 &&
	flux account add-queue gold --priority=1000
'

test_expect_success 'add three different associations' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account add-user --username=${username} --userid=${uid} --bank=A --queues=bronze,silver,gold &&
	flux account add-user --username=${username} --userid=${uid} --bank=B --queues=bronze,silver,gold &&
	flux account add-user --username=${username} --userid=${uid} --bank=C --queues=bronze,silver,gold
'

test_expect_success 'edit the associations to have different fairshare values' '
	flux account edit-user ${username} --bank=A --fairshare=0.99 &&
	flux account edit-user ${username} --bank=B --fairshare=0.50 &&
	flux account edit-user ${username} --bank=C --fairshare=0.08
'

test_expect_success 'configure flux with those queues' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	[queues.silver]
	[queues.gold]
	EOT
	flux config reload
'

test_expect_success 'configure priority plugin with bank factor weight' '
	flux account edit-factor --factor=bank --weight=1000
'

test_expect_success 'send flux-accounting information to the plugin' '
	flux account-priority-update -p ${DB_PATH}
'

# Submit three different jobs to different banks but under the same queue.
# job priority = (bank priority * bank weight)
#                + (queue priority * queue weight)
#                + (fairshare * fairshare weight)
#
# job 1 priority calculation:
# priority = (bank A priority * bank weight)
#            + (bronze queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (100 * 1000) + (1 * 10000) + (0.99 * 100000)
# priority = 100000 + 10000 + 99000
# priority = 209000
test_expect_success 'submit job 1' '
	job1=$(flux submit -S bank=A --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 -f json ${job1} priority \
		| jq '.context.priority' > job1.priority &&
	grep "209000" job1.priority
'

# job 2 priority calculation:
# priority = (bank B priority * bank weight)
#            + (bronze queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (10 * 1000) + (1 * 10000) + (0.50 * 100000)
# priority = 10000 + 10000 + 50000
# priority = 70000
test_expect_success 'submit job 2' '
	job2=$(flux submit -S bank=B --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 -f json ${job2} priority \
		| jq '.context.priority' > job2.priority &&
	grep "70000" job2.priority
'

# job 3 priority calculation:
# priority = (bank C priority * bank weight)
#            + (bronze queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (1 * 1000) + (1 * 10000) + (0.08 * 100000)
# priority = 1000 + 10000 + 8000
# priority = 19000
test_expect_success 'submit job 3' '
	job3=$(flux submit -S bank=C --queue=bronze sleep 60) &&
	flux job wait-event -vt 5 -f json ${job3} priority \
		| jq '.context.priority' > job3.priority &&
	grep "19000" job3.priority
'

test_expect_success 'passing in a username that is not found in flux-accounting DB fails' '
	test_must_fail flux account jobs foo > error_association.out 2>&1 &&
	grep "could not find entry for foo in association_table" error_association.out
'

# By default, we can just specify a username and fetch all of their jobs under
# every bank and every queue. Make sure that each job returns the correct
# priority.
test_expect_success 'call flux account jobs (returns all user jobs)' '
	flux account jobs ${username} > all_jobs.out &&
	grep "${job1}" all_jobs.out | grep 209000 &&
	grep "${job2}" all_jobs.out | grep 70000 &&
	grep "${job3}" all_jobs.out | grep 19000
'

# We can filter to only return jobs that are running under a certain bank but
# are running under any queue.
test_expect_success 'filter jobs by a specific bank' '
	flux account jobs ${username} --bank=A > bank_A_jobs.out &&
	grep "${job1}" bank_A_jobs.out | grep 209000
'

# We can filter to only return jobs that are running under a certain queue but
# are running under any bank.
test_expect_success 'filter jobs by a specific queue' '
	flux account jobs ${username} --queue=bronze > queue_bronze_jobs.out &&
	grep "${job1}" queue_bronze_jobs.out | grep 209000 &&
	grep "${job2}" queue_bronze_jobs.out | grep 70000 &&
	grep "${job3}" queue_bronze_jobs.out | grep 19000
'

# Submit two different jobs to different queues but the same bank.
# job 4 priority calculation:
# priority = (bank C priority * bank weight)
#            + (silver queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (1 * 1000) + (100 * 10000) + (0.08 * 100000)
# priority = 1000 + 1000000 + 8000
# priority = 1009000
test_expect_success 'submit job 4' '
	job4=$(flux submit -S bank=C --queue=silver sleep 60) &&
	flux job wait-event -vt 5 -f json ${job4} priority \
		| jq '.context.priority' > job4.priority &&
	grep "1009000" job4.priority
'

# job 5 priority calculation:
# priority = (bank C priority * bank weight)
#            + (gold queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (1 * 1000) + (1000 * 10000) + (0.08 * 100000)
# priority = 1000 + 10000000 + 8000
# priority = 10009000
test_expect_success 'submit job 5' '
	job5=$(flux submit -S bank=C --queue=gold sleep 60) &&
	flux job wait-event -vt 5 -f json ${job5} priority \
		| jq '.context.priority' > job5.priority &&
	grep "10009000" job5.priority
'

test_expect_success 'filter jobs by the silver queue' '
	flux account jobs ${username} --queue=silver > queue_silver_jobs.out &&
	grep "${job4}" queue_silver_jobs.out | grep 1009000
'

test_expect_success 'filter jobs by the gold queue' '
	flux account jobs ${username} --queue=gold > queue_gold_jobs.out &&
	grep "${job5}" queue_gold_jobs.out | grep 10009000
'

test_expect_success 'run flux account jobs with a format string' '
	flux account jobs ${username} \
		--bank=C \
		-o "{BANK:<8} | {PRIORITY:<10}" \
		> bank_C_jobs.format_string &&
	grep "BANK     | PRIORITY" bank_C_jobs.format_string &&
	grep "C        | 10009000" bank_C_jobs.format_string &&
	grep "C        | 1009000" bank_C_jobs.format_string &&
	grep "C        | 19000"  bank_C_jobs.format_string
'

# We can pass multiple filters to refine the search both by queue and by bank.
test_expect_success 'filter jobs by queue and by bank' '
	flux account jobs ${username} \
		--bank=C --queue=gold \
		-o "{BANK:<8} | {QUEUE:<6} | {PRIORITY:<10}" \
		> multiple_filters.out &&
	grep "BANK     | QUEUE  | PRIORITY" multiple_filters.out &&
	grep "C        | gold   | 10009000" multiple_filters.out
'

test_expect_success 'cancel jobs' '
	flux cancel ${job1} &&
	flux cancel ${job2} &&
	flux cancel ${job3} &&
	flux cancel ${job4} &&
	flux cancel ${job5}
'

test_expect_success 'remove queues from the flux-accounting DB' '
	flux account edit-user ${username} --queues=-1 &&
	flux account delete-queue bronze &&
	flux account delete-queue silver &&
	flux account delete-queue gold &&
	flux account-priority-update -p ${DB_PATH}
'

# job 6 priority calculation:
# priority = (bank C priority * bank weight)
#            + (NO queue priority * queue weight)
#            + (user fairshare * fairshare weight)
# priority = (1 * 1000) + (0 * 10000) + (0.08 * 100000)
# priority = 1000 + 0 + 8000
# priority = 9000
test_expect_success 'submit a job to one of the queues' '
	job6=$(flux submit -S bank=C --queue=gold sleep 60) &&
	flux job wait-event -vt 5 -f json ${job6} priority \
		| jq '.context.priority' > job6.priority &&
	grep "9000" job6.priority
'

# We should still be able to filter jobs by queue even if queues are not
# configured in flux-accounting.
test_expect_success 'filter jobs by gold queue' '
	flux account jobs ${username} --bank=C --queue=gold > no_configured_queues.out &&
	grep "${job6}" no_configured_queues.out | grep 9000
'

test_expect_success 'cancel job6' '
	flux cancel ${job6}
'

test_expect_success 'trying to filter jobs by bad state will raise an error' '
	test_must_fail flux account jobs ${username} --filter=foo > bad_state.err 2>&1 &&
	grep "Invalid filter specified: foo" bad_state.err
'

test_expect_success 'filter jobs by canceled state (expect 6 results)' '
	flux account jobs ${username} --filter=canceled > canceled_jobs.out &&
	grep ${job1} canceled_jobs.out &&
	grep ${job2} canceled_jobs.out &&
	grep ${job3} canceled_jobs.out &&
	grep ${job4} canceled_jobs.out &&
	grep ${job5} canceled_jobs.out &&
	grep ${job6} canceled_jobs.out
'

test_expect_success 'filter jobs by running state (expect 0 results)' '
	flux account jobs ${username} --filter=running > no_results.out &&
	test_must_fail grep ${job1} no_results.out &&
	test_must_fail grep ${job2} no_results.out &&
	test_must_fail grep ${job3} no_results.out &&
	test_must_fail grep ${job4} no_results.out &&
	test_must_fail grep ${job5} no_results.out &&
	test_must_fail grep ${job6} no_results.out
'

test_expect_success 'submit a job and make sure we can filter for it' '
	job7=$(flux submit -S bank=C --queue=gold sleep 60) &&
	flux job wait-event -vt 3 ${job7} priority &&
	flux account jobs ${username} --filter=pending > pending_jobs.out &&
	test_must_fail grep ${job1} pending_jobs.out &&
	test_must_fail grep ${job2} pending_jobs.out &&
	test_must_fail grep ${job3} pending_jobs.out &&
	test_must_fail grep ${job4} pending_jobs.out &&
	test_must_fail grep ${job5} pending_jobs.out &&
	test_must_fail grep ${job6} pending_jobs.out &&
	grep ${job7} pending_jobs.out
'

test_expect_success 'multiple filters can be passed' '
	flux account jobs ${username} --filter=pending,canceled > multiple_filters.out &&
	grep ${job1} multiple_filters.out &&
	grep ${job2} multiple_filters.out &&
	grep ${job3} multiple_filters.out &&
	grep ${job4} multiple_filters.out &&
	grep ${job5} multiple_filters.out &&
	grep ${job6} multiple_filters.out &&
	grep ${job7} multiple_filters.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
