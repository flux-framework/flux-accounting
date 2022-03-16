#!/bin/bash

test_description='Tests for update-usage command'

. $(dirname $0)/sharness.sh

DB_PATH=$(pwd)/FluxAccountingTest.db
ARCHIVEDIR=`pwd`
ARCHIVEDB="${ARCHIVEDIR}/jobarchive.db"
QUERYCMD="flux python ${SHARNESS_TEST_SRCDIR}/scripts/query.py"

export FLUX_CONF_DIR=$(pwd)
test_under_flux 4 job

# wait for job to be stored in job archive
# arg1 - jobid
# arg2 - database path
wait_db() {
		local jobid=$(flux job id $1)
		local dbpath=$2
		local i=0
		query="select id from jobs;"
		while ! ${QUERYCMD} -t 100 ${dbpath} "${query}" | grep $jobid > /dev/null \
			   && [ $i -lt 50 ]
		do
				sleep 0.1
				i=$((i + 1))
		done
		if [ "$i" -eq "50" ]
		then
			return 1
		fi
		return 0
}

test_expect_success 'create flux-accounting DB' '
	flux account -p $(pwd)/FluxAccountingTest.db create-db
'

test_expect_success 'add some banks to the DB' '
	flux account -p ${DB_PATH} add-bank root 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account1 1 &&
	flux account -p ${DB_PATH} add-bank --parent-bank=root account2 1
'

test_expect_success 'add some users to the DB' '
	username=$(whoami) &&
	uid=$(id -u) &&
	flux account -p ${DB_PATH} add-user --username=$username --userid=$uid --bank=account1 --shares=1 &&
	flux account -p ${DB_PATH} add-user --username=$username --userid=$uid --bank=account2 --shares=1 &&
	flux account -p ${DB_PATH} add-user --username=user5011 --userid=5011 --bank=account1 --shares=1 &&
	flux account -p ${DB_PATH} add-user --username=user5012 --userid=5012 --bank=account1 --shares=1
'

test_expect_success 'flux account-shares works' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db
'

test_expect_success 'job-archive: set up config file' '
		cat >archive.toml <<EOF &&
[archive]
dbpath = "${ARCHIVEDB}"
period = "0.5s"
busytimeout = "0.1s"
EOF
	flux config reload
'

test_expect_success 'load job-archive module' '
	flux module load job-archive
'

test_expect_success 'submit some sleep 1 jobs under one user' '
	jobid1=$(flux mini submit -N 1 sleep 1) &&
	jobid2=$(flux mini submit -N 1 sleep 1) &&
	jobid3=$(flux mini submit -n 2 -N 2 sleep 1) &&
	wait_db $jobid1 ${ARCHIVEDB} &&
	wait_db $jobid2 ${ARCHIVEDB} &&
	wait_db $jobid3 ${ARCHIVEDB}
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account -p ${DB_PATH} update-usage ${ARCHIVEDB} &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > post_update1.test &&
	grep "account1" post_update1.test | grep "4" | grep "0.25"
'

test_expect_success 'submit some sleep 1 jobs under the secondary bank of the same user ' '
	jobid1=$(flux mini submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid2=$(flux mini submit --setattr=system.bank=account2 -N 1 sleep 1) &&
	jobid3=$(flux mini submit --setattr=system.bank=account2 -n 2 -N 2 sleep 1) &&
	wait_db $jobid1 ${ARCHIVEDB} &&
	wait_db $jobid2 ${ARCHIVEDB} &&
	wait_db $jobid3 ${ARCHIVEDB}
'

test_expect_success 'run update-usage and update-fshare commands' '
	flux account -p ${DB_PATH} update-usage ${ARCHIVEDB} &&
	flux account-update-fshare -p ${DB_PATH}
'

test_expect_success 'check that job usage and fairshare values get updated' '
	flux account-shares -p $(pwd)/FluxAccountingTest.db > post_update2.test &&
	grep "account2" post_update2.test | grep "4" | grep "0.5"
'

test_expect_success 'remove flux-accounting DB' '
	rm $(pwd)/FluxAccountingTest.db
'

test_expect_success 'job-archive: unload module' '
	flux module unload job-archive
'

test_done
