#!/bin/bash

test_description='Test print-hierarchy command'
. `dirname $0`/sharness.sh
PRINT_HIERARCHY=${FLUX_BUILD_DIR}/src/fairness/print_hierarchy/print_hierarchy
SMALL_NO_TIE=${FLUX_BUILD_DIR}/src/fairness/weighted_tree/test/accounting_db_data/small_no_tie.db
SMALL_TIE=${FLUX_BUILD_DIR}/src/fairness/weighted_tree/test/accounting_db_data/small_tie.db
SMALL_TIE_ALL=${FLUX_BUILD_DIR}/src/fairness/weighted_tree/test/accounting_db_data/small_tie_all.db

test_expect_success 'create hierarchy output from C++ - small_no_tie.db' '
	${PRINT_HIERARCHY} ${SMALL_NO_TIE} > test_small_no_tie.txt
'

test_expect_success 'create expected output - small_no_tie.db' '
	echo "Account|Username|RawShares|RawUsage
root||1000|133
 account1||1000|121
  account1|leaf.1.1|10000|100
  account1|leaf.1.2|1000|11
  account1|leaf.1.3|100000|10
 account2||100|11
  account2|leaf.2.1|100000|8
  account2|leaf.2.2|10000|3
 account3||10|1
  account3|leaf.3.1|100|0
  account3|leaf.3.2|10|1
" > small_no_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_no_tie.db' '
	test_cmp small_no_tie.txt test_small_no_tie.txt
'


test_expect_success 'create hierarchy output from C++ - small_tie.db' '
        ${PRINT_HIERARCHY} ${SMALL_TIE} > test_small_tie.txt
'

test_expect_success 'create expected output - small_tie.db' '
        echo "Account|Username|RawShares|RawUsage
root||1000|133
 account1||1000|120
  account1|leaf.1.1|10000|100
  account1|leaf.1.2|1000|10
  account1|leaf.1.3|100000|10
 account2||100|12
  account2|leaf.2.1|10000|10
  account2|leaf.2.2|1000|1
  account2|leaf.2.3|100000|1
 account3||10|1
  account3|leaf.3.1|100|0
  account3|leaf.3.2|10|1
" > small_tie.txt
'

test_expect_success 'compare hierarchy outputs - small_tie.db' '
        test_cmp small_tie.txt test_small_tie.txt
'


test_expect_success 'create hierarchy output from C++ - small_tie_all.db' '
        ${PRINT_HIERARCHY} ${SMALL_TIE_ALL} > test_small_tie_all.txt
'

test_expect_success 'create expected output - small_tie_all.db' '
        echo "Account|Username|RawShares|RawUsage
root||1000|1332
 account1||1000|120
  account1|leaf.1.1|10000|100
  account1|leaf.1.2|1000|10
  account1|leaf.1.3|100000|10
 account2||100|12
  account2|leaf.2.1|10000|10
  account2|leaf.2.2|1000|1
  account2|leaf.2.3|100000|1
 account3||10000|1200
  account3|leaf.3.1|10000|1000
  account3|leaf.3.2|1000|100
  account3|leaf.3.3|100000|100
" > small_tie_all.txt
'

test_expect_success 'compare hierarchy outputs - small_tie_all.db' '
        test_cmp small_tie_all.txt test_small_tie_all.txt
'

test_done
