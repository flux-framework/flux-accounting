#!/bin/bash

test_description='test rebuilding project usage from retained jobs'

. `dirname $0`/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'allow guest access to testexec' '
	flux config load <<-EOF
	[exec.testexec]
	allow-guests = true
	EOF
'

test_expect_success 'rebuild-project-usage help works' '
	flux account-rebuild-project-usage --help
'

test_expect_success 'rebuild-project-usage rejects a bad database path' '
	test_must_fail flux account-rebuild-project-usage -p missing.db \
		>bad-path.out 2>&1 &&
	grep "error opening DB: unable to open database file missing.db" bad-path.out
'

test_expect_success 'create an empty flux-accounting database' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add banks, associations, projects to DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-project P1 &&
	flux account add-user \
		--username=user1 \
		--userid=50001 \
		--bank=A \
		--projects=P1
'

test_expect_success 'populate the database with a pending project job' '
	cat >populate.py <<-EOF &&
	import json
	import sqlite3
	import sys
	conn = sqlite3.connect(sys.argv[1])
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
		"(id,userid,t_submit,t_run,t_inactive,ranks,R,jobspec,project,bank) "
		"VALUES (?,?,?,?,?,?,?,?,?,?)",
		(1, 50001, 0, 10, 20, "0", resources, jobspec, "P1", "A"),
	)
	conn.commit()
	conn.close()
	EOF
	flux python populate.py ${DB_PATH}
'

test_expect_success 'rebuild-project-usage replaces project totals' '
	${QUERYCMD} ${DB_PATH} \
		"UPDATE project_table SET usage=42.0 WHERE project=\"P1\"" &&
	flux account-rebuild-project-usage -p ${DB_PATH} \
		>rebuild.out 2>&1 &&
	${QUERYCMD} ${DB_PATH} \
		"SELECT usage FROM project_table WHERE project=\"P1\"" >usage.out &&
	grep "usage = 10.0" usage.out &&
	grep "rebuilding uses retained jobs only" rebuild.out
'

test_expect_success 'association processing does not double count the rebuilt job' '
	flux account-update-usage -p ${DB_PATH} &&
	${QUERYCMD} ${DB_PATH} \
		"SELECT usage FROM project_table WHERE project=\"P1\"" >usage.out &&
	grep "usage = 10.0" usage.out
'

test_done
