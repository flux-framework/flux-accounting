#!/bin/bash

test_description='test using short options for various flux-accounting commands'

. `dirname $0`/sharness.sh

mkdir -p conf.d

DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d -Slog-stderr-level=1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add a root bank' '
	flux account add-bank root 1
'

test_expect_success 'add a bank with a short option' '
	flux account add-bank --parent-bank=root A 1
'

test_expect_success 'add a queue with short options' '
	flux account add-queue gold \
		-N 64 \
		-t 3600 \
		-P 1000 &&
	flux account view-queue gold
'

test_expect_success 'edit a queue with short options' '
	flux account edit-queue gold \
		-N 32 \
		-t 1800 \
		-P 500 &&
	flux account view-queue gold
'

test_expect_success 'add a project' '
	flux account add-project project1
'

test_expect_success 'add an association with short options' '
	flux account add-user \
		-u user1 \
		-i 50001 \
		-B A \
		-N 1000 \
		-c 2000 \
		-q gold \
		-P project1
'

test_expect_success 'list associations with short options' '
	flux account list-users -B A
'

test_expect_success 'edit an association with short options' '
	flux account edit-user user1 \
		-N 2000 \
		-c 4000 &&
	flux account view-user user1
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
