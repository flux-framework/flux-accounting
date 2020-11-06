#!/bin/bash

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

rm py-output.txt cpp-output.txt FluxAccounting.db db_creation.log

exit $RC
