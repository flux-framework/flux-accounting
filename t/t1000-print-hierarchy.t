#!/bin/bash

test_description='Test print-hierarchy command'
. `dirname $0`/sharness.sh
ACCT_CLI=${FLUX_SOURCE_DIR}/src/bindings/python/flux/accounting/flux-account.py
PRINT_HIERARCHY=${FLUX_BUILD_DIR}/src/fairness/print_hierarchy/print_hierarchy

test_expect_success 'create valid flux-accounting DB with a proper hierarchy' '
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db create-db &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank A 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=A B 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=B D 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=B E 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=A C 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=C F 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-bank --parent-bank=C G 1 &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-user --username=user1 --account=D &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-user --username=user2 --account=F &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-user --username=user3 --account=F &&
	${PYTHON} ${ACCT_CLI} -p ./FluxAccounting.db add-user --username=user4 --account=G
'

test_expect_success 'create hierarchy output from Python' '
	python3 ${ACCT_CLI} -p ./FluxAccounting.db print-hierarchy > py-output.txt
'

test_expect_success 'create hierarchy output from C++' '
	${PRINT_HIERARCHY} FluxAccounting.db > cpp-output.txt
'

test_expect_success 'compare hierarchy outputs' '
	test_cmp py-output.txt cpp-output.txt
'

test_expect_success 'create valid flux-accounting DB with no entries in bank table' '
	python3 ${ACCT_CLI} -p ./FluxAccounting-2.db create-db 
'

test_expect_success 'print flux-accounting DB with no entries in bank table' '
	test_must_fail ${PRINT_HIERARCHY} FluxAccounting-2.db > error-output.txt 2>&1
'

test_expect_success 'check print error message on empty DB' '
	grep -q "root bank not found, exiting" ./error-output.txt
'

test_done
