#!/bin/bash

test_description='test using short options for various flux-accounting commands'

. `dirname $0`/sharness.sh

mkdir -p conf.d

DB_PATH=$(pwd)/FluxAccountingTest.db

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

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
		-a 1 \
		-m 64 \
		-t 3600 \
		-P 1000 \
		-r 8 &&
	flux account view-queue gold
'

test_expect_success 'edit a queue with short options' '
	flux account edit-queue gold \
		-a 8 \
		-m 32 \
		-t 1800 \
		-P 500 \
		-r 2 &&
	flux account view-queue gold
'

test_expect_success 'add a project' '
	flux account add-project project1
'

test_expect_success 'add an association with short options' '
	flux account add-user \
		-u user1 \
		-i 50001 \
		-b A \
		-s 12345 \
		-f 0.75 \
		-r 100 \
		-a 500 \
		-N 1000 \
		-n 2000 \
		-q gold \
		-P project1 \
		-k project1
'

test_expect_success 'list associations with short options' '
	flux account list-users -c 1 -b A
'

test_expect_success 'edit an association with short options' '
	flux account edit-user user1 \
		-s 9999 \
		-f 0.25 \
		-r 200 \
		-a 600 \
		-N 2000 \
		-n 4000 \
		-k -1 &&
	flux account view-user user1
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
