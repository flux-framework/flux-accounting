#!/bin/bash

test_description='test that held SCHED jobs are not over-released when one slot opens'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

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

# Setting max-sched-jobs to 2 means the association can have up to 2 jobs in
# SCHED state at any given time. With one job consuming all resources, two
# jobs can sit in SCHED while any further submissions get held. When the
# running job is cancelled, exactly *one* SCHED slot opens, so exactly one
# held job has its dependency removed.
test_expect_success 'add association' '
	flux account add-user \
		--username=user1 \
		--bank=A \
		--userid=50001 \
		--max-sched-jobs=2
'

test_expect_success 'load priority plugin' '
	flux jobtap load -r .priority-default \
		${MULTI_FACTOR_PRIORITY} "config=$(flux account export-json)" &&
	flux jobtap list | grep mf_priority
'

test_expect_success 'association is in priority plugin data structure' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_sched_jobs == 2" <query.json
'

# This job consumes all current resources of the instance, so any job submitted
# while it is running will be placed in SCHED state
test_expect_success 'first job proceeds to RUN immediately' '
	job1=$(flux python ${SUBMIT_AS} 50001 -N4 sleep inf) &&
	flux job wait-event -t 5 ${job1} alloc
'

# Two jobs fit within the max-sched-jobs limit of 2 and sit in SCHED state
test_expect_success 'two jobs enter SCHED state' '
	job2=$(flux python ${SUBMIT_AS} 50001 -N4 sleep inf) &&
	flux job wait-event -t 5 ${job2} priority &&
	job3=$(flux python ${SUBMIT_AS} 50001 -N2 sleep inf) &&
	flux job wait-event -t 5 ${job3} priority
'

# The association is now at their max-sched-jobs limit, so the next two
# submitted jobs each get held with the per-association dependency
test_expect_success 'third and fourth jobs get held due to max-sched-jobs limit' '
	job4=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job4} dependency-add &&
	job5=$(flux python ${SUBMIT_AS} 50001 -N1 sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job5} dependency-add
'

test_expect_success 'job counts reflect two held jobs' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json
'

# Cancelling the single running job lets job2 transition to RUN, which
# decrements cur_sched_jobs by one and opens exactly *one* SCHED slot. Only
# job4 (the first held job) should have its dependency removed.
test_expect_success 'cancelled running job releases exactly one held job' '
	flux cancel ${job1} &&
	flux job wait-event -t 5 ${job2} alloc &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job4} dependency-remove
'

# job5 remains in DEPEND state after job4 is released
test_expect_success 'job5 is still held' '
	job5_dec=$(flux job id -t dec ${job5}) &&
	flux jobtap query mf_priority.so > query.json &&
	cat query.json | jq &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job5_dec}\"].deps | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${job5_dec}\"].deps[0] \
			== \"max-sched-jobs-user-limit\"" <query.json
'

# test_expect_success 'cancel jobs' '
#     flux cancel ${job2} ${job3} ${job4} ${job5}
# '

# When job4 (now released) transitions to RUN, cur_sched_jobs decrements again,
# opening the second slot. *Now* job5 can be released.
test_expect_success 'cancel job2 releases the second held job' '
	flux cancel ${job2} &&
	flux job wait-event -t 5 ${job4} alloc &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-user-limit" \
		${job5} dependency-remove
'

test_expect_success 'cancel jobs' '
	flux cancel ${job3} ${job4} ${job5}
'

# Repeat the regression check at the per-queue level. The bronze queue has its
# own max-sched-jobs limit of 2, independent of the per-association limit, so a
# single opened slot in the queue must release exactly one queue-held job.
test_expect_success 'reset association limit and add a queue' '
	flux account add-queue bronze --max-sched-jobs=2 &&
	flux account edit-user user1 --max-sched-jobs=-1 --queues=bronze &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'configure flux with the bronze queue' '
	cat >config/queues.toml <<-EOT &&
	[queues.bronze]
	EOT
	flux config reload &&
	flux queue start --all
'

test_expect_success 'first job in bronze consumes all resources' '
	qjob1=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${qjob1} alloc
'

test_expect_success 'two jobs enter SCHED state in bronze' '
	qjob2=$(flux python ${SUBMIT_AS} 50001 -N4 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${qjob2} priority &&
	qjob3=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${qjob3} priority
'

test_expect_success 'next two bronze jobs get held on per-queue limit' '
	qjob4=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${qjob4} dependency-add &&
	qjob5=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${qjob5} dependency-add
'

test_expect_success 'per-queue job counts reflect two held jobs' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"bronze\"].cur_sched_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json
'

test_expect_success 'cancel runner releases exactly one queue-held job' '
	flux cancel ${qjob1} &&
	flux job wait-event -t 5 ${qjob2} alloc &&
	flux job wait-event -t 5 \
		--match-context=description="max-sched-jobs-queue-limit" \
		${qjob4} dependency-remove
'

test_expect_success 'the second queue-held job is still held' '
	qjob5_dec=$(flux job id -t dec ${qjob5}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${qjob5_dec}\"].deps[0] \
			== \"max-sched-jobs-queue-limit\"" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${qjob2} ${qjob3} ${qjob4} ${qjob5}
'

# Repeat the regression check for the per-association max-run-jobs limit
test_expect_success 'reset queue limit and set a per-association max-run-jobs limit' '
	flux account edit-user user1 \
		--max-sched-jobs=-1 \
		--max-running-jobs=2 \
		--queues=bronze &&
	flux account edit-queue bronze --max-sched-jobs=-1 &&
	flux account-priority-update -p ${DB} &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].max_run_jobs == 2" <query.json
'

# Two jobs can proceed to RUN immediately
test_expect_success 'two jobs proceed to RUN' '
	rjob1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${rjob1} alloc &&
	rjob2=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${rjob2} alloc
'

# The association is now at their max-run-jobs limit, so the next two submitted
# jobs each get held with the per-association max-run-jobs dependency
test_expect_success 'next two jobs get held due to max-run-jobs limit' '
	rjob3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${rjob3} dependency-add &&
	rjob4=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${rjob4} dependency-add
'

test_expect_success 'run-jobs counts reflect two held jobs' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json
'

# Cancelling one running job decrements cur_run_jobs by one and opens exactly
# *one* run slot. Only rjob3 should be released
test_expect_success 'cancelled running job releases exactly one held job' '
	flux cancel ${rjob1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${rjob3} dependency-remove
'

# rjob4 remains held after rjob3 is released
test_expect_success 'the second held job is still held' '
	rjob4_dec=$(flux job id -t dec ${rjob4}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${rjob4_dec}\"].deps | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${rjob4_dec}\"].deps[0] \
			== \"max-running-jobs-user-limit\"" <query.json
'

# When rjob3 (now released) transitions to RUN and then is cancelled, another
# run slot opens and rjob4 can finally be released
test_expect_success 'cancel another running job releases the second held job' '
	flux job wait-event -t 5 ${rjob3} alloc &&
	flux cancel ${rjob2} &&
	flux job wait-event -t 5 \
		--match-context=description="max-running-jobs-user-limit" \
		${rjob4} dependency-remove
'

test_expect_success 'cancel rest of jobs' '
	flux cancel ${rjob3} ${rjob4}
'

# Repeat the regression check for the per-queue max-run-jobs limit. The bronze
# queue is given a max_running_jobs limit of 2 while the per-association
# max-run-jobs limit is reset, so jobs are held on the per-queue
# max-run-jobs-queue dependency only.
test_expect_success 'reset association limit and set a per-queue max-run-jobs limit' '
	flux account edit-user user1 --max-running-jobs=-1 &&
	flux account edit-queue bronze --max-running-jobs=2 &&
	flux account-priority-update -p ${DB}
'

test_expect_success 'two jobs run concurrently up to the per-queue max-run-jobs limit' '
	rqjob1=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${rqjob1} alloc &&
	rqjob2=$(flux python ${SUBMIT_AS} 50001 -N2 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 ${rqjob2} alloc
'

test_expect_success 'next two bronze jobs get held on per-queue max-run-jobs limit' '
	rqjob3=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${rqjob3} dependency-add &&
	rqjob4=$(flux python ${SUBMIT_AS} 50001 -N1 --queue=bronze sleep inf) &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${rqjob4} dependency-add
'

test_expect_success 'per-queue run-jobs counts reflect two held jobs' '
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e ".mf_priority_map[] | \
		select(.userid == 50001) | \
		.banks[0].queue_usage[\"bronze\"].cur_run_jobs == 2" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 2" <query.json
'

test_expect_success 'cancelled running job releases exactly one queue-held job' '
	flux cancel ${rqjob1} &&
	flux job wait-event -t 5 \
		--match-context=description="max-run-jobs-queue" \
		${rqjob3} dependency-remove
'

test_expect_success 'the second queue-held job is still held' '
	rqjob4_dec=$(flux job id -t dec ${rqjob4}) &&
	flux jobtap query mf_priority.so > query.json &&
	test_debug "jq -S . <query.json" &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs | length == 1" <query.json &&
	jq -e \
		".mf_priority_map[] |
		 select(.userid == 50001) |
		 .banks[0].held_jobs[\"${rqjob4_dec}\"].deps[0] \
			== \"max-run-jobs-queue\"" <query.json
'

test_expect_success 'cancel jobs' '
	flux cancel ${rqjob2} ${rqjob3} ${rqjob4}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
