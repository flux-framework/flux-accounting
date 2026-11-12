#!/bin/bash

test_description='test periodic usage decay after repairing an association userid'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

# Drive the full usage updater with fixed timestamps, while exercising userid
# edits and synchronization through the accounting service. No jobs need to
# run and no wall-clock delay is needed to cross a half-life boundary.
test_expect_success 'create deterministic usage helper' '
	cat >usage_helper.py <<-EOF
	import json
	import sqlite3
	import sys
	from unittest import mock
	from fluxacct.jobs.usage import update_job_usage

	conn = sqlite3.connect("file:" + sys.argv[1] + "?mode=rw", uri=True)
	command = sys.argv[2]
	with conn:
	    if command == "seed":
	        conn.execute(
	            "UPDATE t_half_life_period_table SET end_half_life_period=1000"
	        )
	        conn.execute("UPDATE association_table SET job_usage=1500")
	        conn.executemany(
	            "UPDATE job_usage_per_association_table SET value=? WHERE period=?",
	            [(1000, 0), (500, 1), (0, 2), (0, 3)],
	        )
	    elif command == "add-job":
	        resources = json.dumps({
	            "version": 1,
	            "execution": {
	                "R_lite": [{"rank": "0", "children": {"core": "0"}}],
	                "starttime": 0,
	                "expiration": 0,
	                "nodelist": ["fluke0"],
	            },
	        })
	        jobspec = json.dumps({"attributes": {"system": {"bank": "A"}}})
	        conn.execute(
	            "INSERT INTO jobs "
	            "(id,userid,t_submit,t_run,t_inactive,ranks,R,jobspec,bank) "
	            "VALUES (?,?,?,?,?,?,?,?,?)",
	            (1, 2002, 1255, 1255, 1270, "0", resources, jobspec, "A"),
	        )
	    elif command == "update":
	        with mock.patch("time.time", return_value=float(sys.argv[3])):
	            update_job_usage(conn)
	    elif command == "userids":
	        association = conn.execute(
	            "SELECT userid FROM association_table WHERE username=? AND bank=?",
	            ("user1", "A"),
	        ).fetchone()[0]
	        factor = conn.execute(
	            "SELECT userid FROM job_usage_factor_table WHERE username=? AND bank=?",
	            ("user1", "A"),
	        ).fetchone()[0]
	        print(json.dumps([association, factor]))
	    elif command == "snapshot":
	        periods = [row[0] for row in conn.execute(
	            "SELECT value FROM job_usage_per_association_table "
	            "WHERE username=? AND bank=? ORDER BY period",
	            ("user1", "A"),
	        )]
	        usage = conn.execute(
	            "SELECT job_usage FROM association_table WHERE username=? AND bank=?",
	            ("user1", "A"),
	        ).fetchone()[0]
	        print(json.dumps({"periods": periods, "job_usage": usage}))
	    else:
	        raise ValueError(command)
	conn.close()
	EOF
'

test_expect_success 'create periodic database with four 100-second bins' '
	flux account -p ${DB_PATH} create-db --decay-method=periodic \
		--priority-decay-half-life=100s --priority-usage-reset-period=400s
'

test_expect_success 'start accounting service and add association' '
	flux account-service -p ${DB_PATH} -t &&
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=1001 --bank=A
'

test_expect_success 'seed history and rotate before changing userid' '
	flux python usage_helper.py ${DB_PATH} seed &&
	flux python usage_helper.py ${DB_PATH} update 1150 &&
	flux python usage_helper.py ${DB_PATH} snapshot >before.out &&
	cat >before.expected <<-EOF &&
	{"periods": [0.0, 500.0, 250.0, 0.0], "job_usage": 750.0}
	EOF
	test_cmp before.expected before.out
'

test_expect_success 'edit-user --userid updates usage-factor userid' '
	flux account edit-user user1 --userid=2002 &&
	flux python usage_helper.py ${DB_PATH} userids >userids.out &&
	echo "[2002, 2002]" >userids.expected &&
	test_cmp userids.expected userids.out
'

test_expect_success 'sync-userids leaves edited userids unchanged' '
	flux account sync-userids &&
	flux python usage_helper.py ${DB_PATH} userids >synced.out &&
	test_cmp userids.expected synced.out
'

test_expect_success 'history still rotates and decays after userid repair' '
	flux python usage_helper.py ${DB_PATH} update 1250 &&
	flux python usage_helper.py ${DB_PATH} snapshot >after.out &&
	cat >after.expected <<-EOF &&
	{"periods": [0.0, 0.0, 250.0, 125.0], "job_usage": 375.0}
	EOF
	test_cmp after.expected after.out
'

test_expect_success 'same-period job adds only its usage to decayed history' '
	flux python usage_helper.py ${DB_PATH} add-job &&
	flux python usage_helper.py ${DB_PATH} update 1275 &&
	flux python usage_helper.py ${DB_PATH} snapshot >job.out &&
	cat >job.expected <<-EOF &&
	{"periods": [15.0, 0.0, 250.0, 125.0], "job_usage": 390.0}
	EOF
	test_cmp job.expected job.out
'

test_expect_success 'shut down accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
