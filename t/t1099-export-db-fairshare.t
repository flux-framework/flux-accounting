#!/bin/bash

test_description='test exporting flux-accounting database for fairshare-emulate'

. `dirname $0`/sharness.sh
DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add banks to the DB' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=C D 1
'

test_expect_success 'add associations to the DB' '
	flux account add-user --username=user1 --userid=50001 --bank=A &&
	flux account add-user --username=user2 --userid=50002 --bank=B &&
	flux account add-user --username=user3 --userid=50003 --bank=D
'

test_expect_success 'export-db --fairshare-emulate produces valid JSON' '
	flux account export-db --fairshare-emulate > export.json &&
	grep "\"root\"" export.json &&
	grep "\"bank\": \"root\"" export.json &&
	grep "\"username\": \"user1\"" export.json
'

test_expect_success 'exported JSON contains all banks' '
	grep "\"bank\": \"root\"" export.json &&
	grep "\"bank\": \"A\"" export.json &&
	grep "\"bank\": \"B\"" export.json &&
	grep "\"bank\": \"C\"" export.json &&
	grep "\"bank\": \"D\"" export.json
'

test_expect_success 'exported JSON contains all users' '
	grep "\"username\": \"user1\"" export.json &&
	grep "\"username\": \"user2\"" export.json &&
	grep "\"username\": \"user3\"" export.json
'

test_expect_success 'exported JSON works with fairshare-emulate' '
	flux account export-db --fairshare-emulate > hierarchy.json &&
	flux account-fairshare-emulate \
		-i hierarchy.json -o "{username},{fairshare}" > results.json &&
	grep "user1,1.0" results.json &&
	grep "user2,1.0" results.json &&
	grep "user3,1.0" results.json
'

test_expect_success 'short option -F also works' '
	flux account export-db -F > export_short.json &&
	grep "\"root\"" export_short.json &&
	grep "\"bank\": \"root\"" export_short.json &&
	grep "\"bank\": \"A\"" export_short.json &&
	grep "\"bank\": \"B\"" export_short.json &&
	grep "\"bank\": \"C\"" export_short.json &&
	grep "\"bank\": \"D\"" export_short.json &&
	grep "\"username\": \"user1\"" export_short.json &&
	grep "\"username\": \"user2\"" export_short.json &&
	grep "\"username\": \"user3\"" export_short.json

'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
