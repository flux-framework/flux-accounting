#!/bin/bash

test_description='test fair-share ordering with fractional sibling usage'

. `dirname $0`/sharness.sh

TEST_DB=$(pwd)/FluxAccountingTest.db
UPDATE_USAGE=${SHARNESS_TEST_SRCDIR}/scripts/update_usage_column.py

export TEST_UNDER_FLUX_NO_JOB_EXEC=y
export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 1 job -Slog-stderr-level=1

set_equal_usage () {
	flux python ${UPDATE_USAGE} ${TEST_DB} user1 "$1" &&
	flux python ${UPDATE_USAGE} ${TEST_DB} user2 "$1" &&
	flux python ${UPDATE_USAGE} ${TEST_DB} user3 "$1"
}

snapshot_fairshare () {
	flux account list-users --json --fields=username,fairshare >users.json &&
	jq -c "sort_by(.username) | map([.username, .fairshare])" users.json
}

compare_fairshare () {
	jq -e -s ".[0] == .[1]" "$1" "$2"
}

test_expect_success 'create flux-accounting DB' '
	flux account -p ${TEST_DB} create-db
'

test_expect_success 'start accounting service and add unequal-share siblings' '
	flux account-service -p ${TEST_DB} -t &&
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-user --username=user1 --userid=50001 --bank=A --shares=1 &&
	flux account add-user --username=user2 --userid=50002 --bank=A --shares=2 &&
	flux account add-user --username=user3 --userid=50003 --bank=A --shares=3
'

# with equal nonzero usage, shares determine rank; uniformly scaling usage
# must preserve the fair-share factors
test_expect_success 'equal integer usage ranks users by shares' '
	set_equal_usage 300 &&
	flux account-update-fshare -p ${TEST_DB} &&
	snapshot_fairshare >integer.out &&
	echo "[[\"user1\",0.333333],[\"user2\",0.666667],[\"user3\",1.0]]" \
		>fairshare.expected &&
	compare_fairshare fairshare.expected integer.out
'

test_expect_success 'fractional usage preserves ordering when total is below one' '
	set_equal_usage 0.3 &&
	flux account-update-fshare -p ${TEST_DB} &&
	snapshot_fairshare >fractional.out &&
	compare_fairshare fairshare.expected fractional.out
'

# each contribution is below one, but their true sum is 1.8; this catches
# truncation on each accumulation step rather than only at the end
test_expect_success 'fractional usage preserves ordering when total exceeds one' '
	set_equal_usage 0.6 &&
	flux account-update-fshare -p ${TEST_DB} &&
	snapshot_fairshare >fractional_sum.out &&
	compare_fairshare fairshare.expected fractional_sum.out
'

test_expect_success 'replace users with one user in each equal-share bank' '
	flux account delete-user user1 A --force &&
	flux account delete-user user2 A --force &&
	flux account delete-user user3 A --force &&
	flux account add-bank --parent-bank=root B 1 &&
	flux account add-user --username=user_A --userid=50001 --bank=A --shares=1 &&
	flux account add-user --username=user_B --userid=50002 --bank=B --shares=1
'

# each bank has one user, so its aggregate usage is that user's usage;
# equal bank shares mean the lower-usage bank must rank higher
test_expect_success 'equal-share banks rank by different integer usage' '
	flux python ${UPDATE_USAGE} ${TEST_DB} user_A 20 &&
	flux python ${UPDATE_USAGE} ${TEST_DB} user_B 80 &&
	flux account-update-fshare -p ${TEST_DB} &&
	snapshot_fairshare >banks_integer.out &&
	echo "[[\"user_A\",1.0],[\"user_B\",0.5]]" >banks.expected &&
	compare_fairshare banks.expected banks_integer.out
'

test_expect_success 'equal-share banks rank by different fractional usage' '
	flux python ${UPDATE_USAGE} ${TEST_DB} user_A 0.2 &&
	flux python ${UPDATE_USAGE} ${TEST_DB} user_B 0.8 &&
	flux account-update-fshare -p ${TEST_DB} &&
	snapshot_fairshare >banks_fractional.out &&
	compare_fairshare banks.expected banks_fractional.out
'

test_expect_success 'shut down accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
