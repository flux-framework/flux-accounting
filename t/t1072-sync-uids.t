#!/bin/bash

test_description='test synchronizing userids across multiple tables'

. `dirname $0`/sharness.sh

mkdir -p config

DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

# create a script to update and get userids from job_usage_factor_table
cat > db_helper.py <<'PYTHON_EOF'
#!/usr/bin/env python3

import sqlite3
import sys

def update_userid(dbpath, username, userid):
	"""Update the userid for an association in job_usage_factor_table"""
	try:
		conn = sqlite3.connect(dbpath)
		cursor = conn.cursor()
		query = "UPDATE job_usage_factor_table SET userid=? WHERE username=?"
		cursor.execute(query, (userid, username))
		conn.commit()
		conn.close()
		return 0
	except sqlite3.Error as e:
		print(f"error updating userid: {e}", file=sys.stderr)
		return 1

def get_userid(dbpath, username):
	"""Get the userid for an association in job_usage_factor_table"""
	try:
		conn = sqlite3.connect(dbpath)
		cursor = conn.cursor()
		query = "SELECT userid FROM job_usage_factor_table WHERE username=?"
		cursor.execute(query, (username,))
		result = cursor.fetchone()
		conn.close()
		if result:
			print(result[0])
			return 0
		else:
			return 1
	except sqlite3.Error as e:
		print(f"error getting userid: {e}", file=sys.stderr)
		return 1

if __name__ == "__main__":
	if len(sys.argv) < 3:
		print("Usage: script.py <command> <dbpath> <username> [userid]", file=sys.stderr)
		sys.exit(1)
	
	command = sys.argv[1]
	dbpath = sys.argv[2]
	username = sys.argv[3]
	
	if command == "update":
		if len(sys.argv) < 5:
			print("Usage: script.py update <dbpath> <username> <userid>", file=sys.stderr)
			sys.exit(1)
		userid = int(sys.argv[4])
		sys.exit(update_userid(dbpath, username, userid))
	elif command == "get":
		sys.exit(get_userid(dbpath, username))
	else:
		print(f"Unknown command: {command}", file=sys.stderr)
		sys.exit(1)
PYTHON_EOF

chmod +x db_helper.py

# update the userid for an association in job_usage_factor_table
update_userid() {
	python3 db_helper.py update "$1" "$2" "$3"
}

# get the userid for an association in job_usage_factor_table
get_userid() {
	python3 db_helper.py get "$1" "$2"
}

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

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add some associations' '
	flux account add-user --username=user1 --userid=50001 --bank=A &&
	flux account add-user --username=user2 --userid=50002 --bank=A &&
	flux account add-user --username=user3 --userid=50003 --bank=A
'

test_expect_success 'call sync-userids when tables are consistent' '
	flux account sync-userids
'

test_expect_success 'ensure userids have not changed' '
	get_userid ${DB} user1 > user1.userid && test 50001 -eq $(cat user1.userid) &&
	get_userid ${DB} user2 > user2.userid && test 50002 -eq $(cat user2.userid) &&
	get_userid ${DB} user3 > user3.userid && test 50003 -eq $(cat user3.userid)
'

test_expect_success 'change uids in job_usage_factor_table to be inconsistent' '
	update_userid ${DB} user1 65534 &&
	get_userid ${DB} user1 > user1.userid && test 65534 -eq $(cat user1.userid) &&
	update_userid ${DB} user2 65534 &&
	get_userid ${DB} user2 > user2.userid && test 65534 -eq $(cat user2.userid) &&
	update_userid ${DB} user3 65534 &&
	get_userid ${DB} user3 > user3.userid && test 65534 -eq $(cat user3.userid)
'

test_expect_success 'call sync-userids to make tables consistent' '
	flux account sync-userids
'

test_expect_success 'check userid for each user' '
	get_userid ${DB} user1 > user1.userid && test 50001 -eq $(cat user1.userid) &&
	get_userid ${DB} user2 > user2.userid && test 50002 -eq $(cat user2.userid) &&
	get_userid ${DB} user3 > user3.userid && test 50003 -eq $(cat user3.userid)
'

test_expect_success 'change only one of the uids in job_usage_factor to be inconsistent' '
	update_userid ${DB} user1 65534 &&
	get_userid ${DB} user1 > user1.userid && test 65534 -eq $(cat user1.userid) &&
	get_userid ${DB} user2 > user2.userid && test 50002 -eq $(cat user2.userid) &&
	get_userid ${DB} user3 > user3.userid && test 50003 -eq $(cat user3.userid)
'

test_expect_success 'call sync-userids to make tables consistent' '
	flux account sync-userids &&
	get_userid ${DB} user1 > user1.userid && test 50001 -eq $(cat user1.userid) &&
	get_userid ${DB} user2 > user2.userid && test 50002 -eq $(cat user2.userid) &&
	get_userid ${DB} user3 > user3.userid && test 50003 -eq $(cat user3.userid)
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
