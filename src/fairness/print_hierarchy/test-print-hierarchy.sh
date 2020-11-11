#!/bin/bash

# TEST 1: valid flux-accounting DB with a proper hierarchy

echo "test 1: valid flux-accounting DB with a proper hierarchy"

python3 ../../../accounting/accounting_cli.py create-db FluxAccounting.db

python3 ../../../accounting/accounting_cli.py add-bank A 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=A B 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=B D 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=B E 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=A C 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=C F 1

python3 ../../../accounting/accounting_cli.py add-bank --parent-bank=C G 1

python3 ../../../accounting/accounting_cli.py add-user --username=user1 --account=D

python3 ../../../accounting/accounting_cli.py add-user --username=user2 --account=F

python3 ../../../accounting/accounting_cli.py add-user --username=user3 --account=F

python3 ../../../accounting/accounting_cli.py add-user --username=user4 --account=G

python3 ../../../accounting/accounting_cli.py print-hierarchy > py-output.txt

./print_hierarchy FluxAccounting.db > cpp-output.txt

diff py-output.txt cpp-output.txt

RC=$?

if [[ $RC = 0 ]]
then
  echo "test 1: success"
  rm py-output.txt cpp-output.txt FluxAccounting.db db_creation.log
else
  exit $RC
fi

# TEST 2: valid flux-accounting DB with no entries should exit out

echo "test 2: valid flux-accounting DB with no entries in bank table"

python3 ../../../accounting/accounting_cli.py create-db FluxAccounting.db

./print_hierarchy FluxAccounting.db > error-output.txt 2>&1

file_contents=`cat error-output.txt`

if [[ $file_contents = 'root bank not found, exiting' ]]
then
  echo "test 2: success"
  rm FluxAccounting.db db_creation.log error-output.txt
else
  exit 1
fi
