#!/bin/bash

test_description='test calculating bank job usage for multi-level hierarchies'

. `dirname $0`/sharness.sh

mkdir -p conf.d

DB_PATH=$(pwd)/FluxAccountingTest.db
UPDATE_USAGE_COL=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -o,--config-path=$(pwd)/conf.d

flux setattr log-stderr-level 1

test_expect_success 'create flux-accounting DB' '
	flux account -p ${DB_PATH} create-db
'

test_expect_success 'start flux-accounting service' '
	flux account-service -p ${DB_PATH} -t
'

test_expect_success 'add some banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-bank --parent-bank=root C 1 &&
	flux account add-bank --parent-bank=C D 1 &&
	flux account add-bank --parent-bank=C E 1
'

test_expect_success 'add three associations to bank A' '
	flux account add-user --username=user1 --userid=50001 --bank=A &&
	flux account add-user --username=user2 --userid=50002 --bank=A &&
	flux account add-user --username=user3 --userid=50003 --bank=A
'

test_expect_success 'add two associations to bank B' '
	flux account add-user --username=user4 --userid=50004 --bank=B &&
	flux account add-user --username=user5 --userid=50005 --bank=B
'

test_expect_success 'add one association to bank D' '
	flux account add-user --username=user6 --userid=50006 --bank=D
'

test_expect_success 'add one association to bank E' '
	flux account add-user --username=user7 --userid=50007 --bank=E
'

test_expect_success 'edit job usage for associations in bank A (total usage = 50)' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user1 20 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user2 20 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user3 10
'

test_expect_success 'edit job usage for associations in bank B (total usage = 25)' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user4 13 &&
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user5 12
'

test_expect_success 'edit job usage for associations in bank D (total usage = 25)' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user6 25
'

test_expect_success 'edit job usage for associations in bank E (total usage = 10)' '
	flux python ${UPDATE_USAGE_COL} ${DB_PATH} user7 10
'

test_expect_success 'call update-usage, update-fshare' '
	flux account-update-usage -p ${DB_PATH} &&
	flux account-update-fshare -p ${DB_PATH}
'

# After updating the job usage and fairshare values for the entire database,
# the hierarchy should look like the following:
#
# Bank                            Username           RawShares            RawUsage           Fairshare
# root                                                       1               110.0
#  A                                                         1                50.0
#   A                                user1                   1                20.0            0.285714
#   A                                user2                   1                20.0            0.285714
#   A                                user3                   1                10.0            0.428571
#  B                                                         1                25.0
#   B                                user4                   1                13.0            0.857143
#   B                                user5                   1                12.0                 1.0
#  C                                                         1                35.0
#   D                                                        1                25.0
#    D                               user6                   1                25.0            0.571429
#   E                                                        1                10.0
#    E                               user7                   1                10.0            0.714286
test_expect_success 'check job usage values for root bank' '
	flux account view-bank root > bank_root_usage.out &&
	grep "\"job_usage\": 110.0" bank_root_usage.out
'

test_expect_success 'check job usage values for bank A' '
	flux account view-bank A > bankA_usage.out &&
	grep "\"job_usage\": 50.0" bankA_usage.out
'

test_expect_success 'check job usage values for bank B' '
	flux account view-bank B > bankB_usage.out &&
	grep "\"job_usage\": 25.0" bankB_usage.out
'

test_expect_success 'check job usage values for bank C' '
	flux account view-bank C > bankC_usage.out &&
	grep "\"job_usage\": 35.0" bankC_usage.out
'

test_expect_success 'check job usage values for bank D' '
	flux account view-bank D > bankD_usage.out &&
	grep "\"job_usage\": 25.0" bankD_usage.out
'

test_expect_success 'check job usage values for bank E' '
	flux account view-bank E > bankE_usage.out &&
	grep "\"job_usage\": 10.0" bankE_usage.out
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
