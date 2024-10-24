#!/bin/bash

test_description='test using common formatter for Python bindings'

. `dirname $0`/sharness.sh

mkdir -p conf.d

ACCOUNTING_DB=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB, start flux-accounting service' '
	flux account -p ${ACCOUNTING_DB} create-db &&
	flux account-service -p ${ACCOUNTING_DB} -t
'

test_expect_success 'call list-banks with no data in bank_table' '
	test_must_fail flux account list-banks > error.out 2>&1 &&
	grep "no results found in query" error.out
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1
'

test_expect_success 'list banks' '
	flux account list-banks
'

test_expect_success 'bad field will result in ValueError' '
	test_must_fail flux account list-banks --fields=foo > error.out 2>&1 &&
	grep "invalid fields: foo" error.out
'

test_expect_success 'customize output' '
	flux account list-banks --fields=bank_id &&
	flux account list-banks --fields=bank_id,bank &&
	flux account list-banks --fields=bank_id,bank,active &&
	flux account list-banks --fields=bank_id,bank,active,parent_bank &&
	flux account list-banks --fields=bank_id,bank,active,parent_bank,shares &&
	flux account list-banks --fields=bank_id,bank,active,parent_bank,shares,job_usage
'

test_expect_success 'include inactive banks' '
	flux account delete-bank A &&
	flux account list-banks --inactive
'

test_expect_success 'list banks in table format' '
	flux account list-banks --table
'

test_expect_success 'customize output in table format' '
	flux account list-banks --table --fields=bank_id &&
	flux account list-banks --table --fields=bank_id,bank &&
	flux account list-banks --table --fields=bank_id,bank,active &&
	flux account list-banks --table --fields=bank_id,bank,active,parent_bank &&
	flux account list-banks --table --fields=bank_id,bank,active,parent_bank,shares &&
	flux account list-banks --table --fields=bank_id,bank,active,parent_bank,shares,job_usage
'

test_expect_success 'include inactive banks in table format' '
	flux account list-banks --table --inactive
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_expect_success 'remove flux-accounting DB' '
	rm ${ACCOUNTING_DB}
'

test_done
