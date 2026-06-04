#!/bin/bash

test_description='test updating fair-share for a DB with huge job usage values'

. `dirname $0`/sharness.sh
TEST_DB=$(pwd)/FluxAccountingTest.db

UPDATE_USAGE=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

test_expect_success 'create small_no_tie flux-accounting DB' '
	flux account -p ${TEST_DB} create-db
'

test_expect_success 'start flux-accounting service on small_no_tie DB' '
	flux account-service -p ${TEST_DB} -t
'

# Two banks with identical shares. Bank A receives a job usage value larger
# than INT_MAX (2147483647); Bank B receives a smaller value that fits in an
# int. Since the shares are equal, the lower-usage bank (B) must end up with a
# higher fair-share for its user than the higher-usage bank (A).
test_expect_success 'add banks with equal shares' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 333333 &&
	flux account add-bank --parent-bank=root B 333333
'

test_expect_success 'add one association to each bank' '
	flux account add-user --username=user_A --bank=A &&
	flux account add-user --username=user_B --bank=B
'

test_expect_success 'set a huge job usage value (> INT_MAX) for user_A' '
	flux python ${UPDATE_USAGE} ${TEST_DB} user_A 9000000000
'

test_expect_success 'set a smaller job usage value (< INT_MAX) for user_B' '
	flux python ${UPDATE_USAGE} ${TEST_DB} user_B 1500000000
'

test_expect_success 'run update-usage and update-fshare' '
	flux account-update-usage -p ${TEST_DB} &&
	flux account-update-fshare -p ${TEST_DB}
'

# After a fair-share update, user_B should have a better fair-share value than
# user_A since their usage is much lower.
test_expect_success 'check fair-share value for user_A' '
	flux account view-user user_A --fields=fairshare > user_A_fairshare.test &&
	grep "0.5" user_A_fairshare.test
'

test_expect_success 'check fair-share value for bankB' '
	flux account view-user user_B --fields=fairshare > user_B_fairshare.test &&
	grep "1.0" user_B_fairshare.test
'

test_expect_success 'remove flux-accounting DB' '
	rm ${TEST_DB}
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
