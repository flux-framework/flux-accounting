#!/bin/bash

test_description='test arbitrarily calculating job usage'

. `dirname $0`/sharness.sh

mkdir -p config

MULTI_FACTOR_PRIORITY=${FLUX_BUILD_DIR}/src/plugins/.libs/mf_priority.so
SUBMIT_AS=${SHARNESS_TEST_SRCDIR}/scripts/submit_as.py
DB=$(pwd)/FluxAccountingTest.db
INSERT_JOBS="flux python ${SHARNESS_TEST_SRCDIR}/scripts/t1075/insert_jobs_to_db.py"

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 16 job -o,--config-path=$(pwd)/config

flux setattr log-stderr-level 1

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

test_expect_success 'add banks' '
	flux account add-bank root 1 &&
	flux account add-bank --parent-bank=root A 1 &&
	flux account add-bank --parent-bank=root B 1
'

test_expect_success 'add associations' '
	flux account add-user --username=u1 --bank=A --userid=50001 &&
	flux account add-user --username=u2 --bank=A --userid=50002 &&
	flux account add-user --username=u3 --bank=B --userid=50003
'

test_expect_success 'view-usage-report -h/--help works' '
	flux account view-usage-report --h
'

# This script will populate the "jobs" table with sample job records for each
# association listed above. The table will be constructed of the following
# records:
#
# user u1 has 5 total job records:
#   1. 2-node job that ran for 60 seconds on January 1st, 2025
#   2. 1-node job that ran for 60 seconds on April 17th, 2025
#   3. 1-node job that ran for 120 seconds on May 20th, 2025
#   4. 4-node job that ran for 60 seconds on November 10th, 2025
# user u2 has 2 total job records:
#   1. 2-node job that ran for 180 seconds on April 18th, 2025
#   2. 1-node job that ran for 60 seconds on December 1st, 2025
# user u3 has 2 total job records:
#   1. 4-node job that ran for 60 seconds on June 1st, 2025
#   1. 2-node job that ran for 30 seconds on June 2nd, 2025
test_expect_success 'insert job records into DB' '
	${INSERT_JOBS} ${DB}
'

# The following set of tests assumes flux-accounting's default method of
# calculating job usage, which is a sum of products between how many nodes the
# job used and its total duration.
#
# u1 job1 = 2 *  60 = 120
# u1 job2 = 1 *  60 =  60
# u1 job3 = 1 * 120 = 120
# u1 job4 = 4 *  60 = 240
# u2 job1 = 2 * 180 = 360
# u2 job2 = 1 *  60 =  60
# u3 job1 = 4 *  60 = 240
# u3 job2 = 2 *  30 =  60
test_expect_success '--start before all jobs calculates total usage' '
	flux account view-usage-report -s 12/01/24 > usage.test1 &&
	grep "TOTAL" usage.test1 &&
	grep "1260" usage.test1
'

test_expect_success '--start in middle of jobs calculates some usage' '
	flux account view-usage-report -s 05/31/25 > usage.test2 &&
	grep "TOTAL" usage.test2 &&
	grep "600" usage.test2
'

test_expect_success '--start after all jobs reports no usage' '
	flux account view-usage-report -s 01/01/9999 > usage.test3 &&
	grep "TOTAL" usage.test3 &&
	grep "0.00" usage.test3
'

test_expect_success '-u: unknown user reports no usage' '
	flux account view-usage-report -s 12/01/24 -u foo > usage.test4 &&
	grep "0.00" usage.test4
'

test_expect_success '-u: u1 has total usage of 540' '
	flux account view-usage-report -s 12/01/24 -u u1 > usage.test5 &&
	grep "540" usage.test5
'

test_expect_success '-u: u2 has total usage of 420' '
	flux account view-usage-report -s 12/01/24 -u u2 > usage.test6 &&
	grep "420" usage.test6
'

test_expect_success '-u: u3 has total usage of 300' '
	flux account view-usage-report -s 12/01/24 -u u3 > usage.test7 &&
	grep "300" usage.test7
'

test_expect_success '-b: bank A has total usage of 960' '
	flux account view-usage-report -s 12/01/24 -b A > usage.test8 &&
	grep "960" usage.test8
'

test_expect_success '-b: bank B has total usage of 300' '
	flux account view-usage-report -s 12/01/24 -b B > usage.test9 &&
	grep "300" usage.test9
'

test_expect_success '-r: bin usage by user' '
	flux account view-usage-report -s 12/01/24 -r byuser > usagebyuser.test1 &&
	grep "50001                            540.00" usagebyuser.test1 &&
	grep "50002                            420.00" usagebyuser.test1 &&
	grep "50003                            300.00" usagebyuser.test1
'

test_expect_success '-r: bin usage by bank' '
	flux account view-usage-report -s 12/01/24 -r bybank > usagebybank.test1 &&
	grep "A                                960.00" usagebybank.test1 &&
	grep "B                                300.00" usagebybank.test1
'

test_expect_success '-r: bin usage by association' '
	flux account view-usage-report -s 12/01/24 -r byassociation > usagebyassoc.test1 &&
	cat usagebyassoc.test1 &&
	grep "A:50001                          540.00" usagebyassoc.test1 &&
	grep "A:50002                          420.00" usagebyassoc.test1 &&
	grep "B:50003                          300.00" usagebyassoc.test1
'

test_expect_success '-t: specify usage by hour' '
	flux account view-usage-report -s 12/01/24 -u u1 -t hour > timeunit.test1 &&
	grep "0.15" timeunit.test1
'

test_expect_success '-t: specify usage by minute' '
	flux account view-usage-report -s 12/01/24 -u u1 -t min > timeunit.test2 &&
	grep "9" timeunit.test2
'

# Calculating job usage by second is how usage is calculated by default.
test_expect_success '-t: specify usage by second' '
	flux account view-usage-report -s 12/01/24 -u u1 -t sec > timeunit.test3 &&
	grep "540.00" timeunit.test3
'

test_expect_success '-S: bin by job sizes of 1,2,3,4 for u1' '
	flux account view-usage-report -s 12/01/24 -u u1 -S 1,2,3,4 > jobsizes.test1 &&
	grep "1+             2+             3+             4+" jobsizes.test1 &&
	grep "180.00         120.00           0.00         240.00" jobsizes.test1
'

test_expect_success '-S: bin by job sizes of 1,2,3,4 for u2' '
	flux account view-usage-report -s 12/01/24 -u u2 -S 1,2,3,4 > jobsizes.test2 &&
	grep "1+             2+             3+             4+" jobsizes.test2 &&
	grep "60.00         360.00           0.00           0.00" jobsizes.test2
'

test_expect_success '-S: bin by job sizes of 1,2,3,4 for u3' '
	flux account view-usage-report -s 12/01/24 -u u3 -S 1,2,3,4 > jobsizes.test3 &&
	grep "1+             2+             3+             4+" jobsizes.test3 &&
	grep "0.00          60.00           0.00         240.00" jobsizes.test3
'

test_expect_success '-e: end date before all jobs shows no usage' '
	flux account view-usage-report -e 01/01/1999 > usageend.test1 &&
	grep "0.00" usageend.test1
'

test_expect_success '-e: end date after all jobs shows all usage' '
	flux account view-usage-report -s 12/31/2024 -e 01/01/9999 > usageend.test2 &&
	grep "1260" usageend.test2
'

test_expect_success '-e: end date after some jobs shows some usage' '
	flux account view-usage-report -s 12/31/2024 -e 06/02/2025 > usageend.test3 &&
	grep "900" usageend.test3
'

test_expect_success 'shut down flux-accounting service' '
	flux python -c "import flux; flux.Flux().rpc(\"accounting.shutdown_service\").get()"
'

test_done
