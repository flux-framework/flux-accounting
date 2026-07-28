#!/bin/bash

test_description='test fair-share emulator'

. `dirname $0`/sharness.sh

mkdir -p config

EXPECTED_FILES=${SHARNESS_TEST_SRCDIR}/expected/fairshare_emulate

export TEST_UNDER_FLUX_SCHED_SIMPLE_MODE="limited=1"
test_under_flux 4 job -o,--config-path=$(pwd)/config -Slog-stderr-level=1

test_expect_success '--help message works' '
	flux account-fairshare-emulate --help
'

test_expect_success 'nonexistent input file raises error' '
	test_must_fail flux account-fairshare-emulate -i foo.json > no_json_file.err 2>&1 &&
	grep "fairshare-emulate: FileNotFoundError: input file not found: foo.json" no_json_file.err
'

test_expect_success 'malformed JSON input raises error' '
	cat <<-EOF >bad.json
	{
		this sure is bad JSON
	}
	EOF
	test_must_fail flux account-fairshare-emulate -i bad.json > bad_json.err 2>&1 &&
	grep -E "(fairshare-emulate)|\
(JSONDecodeError)|\
(Expecting property name enclosed in double quotes)" bad_json.err
'

test_expect_success 'create small_no_tie JSON input' '
	cat <<-EOF >small_no_tie.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 133,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 121,
			"children": [
			  {"username": "leaf.1.1", "shares": 10000, "usage": 100},
			  {"username": "leaf.1.2", "shares": 1000, "usage": 11},
			  {"username": "leaf.1.3", "shares": 100000, "usage": 10}
			]
		  },
		  {
			"bank": "account2",
			"shares": 100,
			"usage": 11,
			"children": [
			  {"username": "leaf.2.1", "shares": 100000, "usage": 8},
			  {"username": "leaf.2.2", "shares": 10000, "usage": 3}
			]
		  },
		  {
			"bank": "account3",
			"shares": 10,
			"usage": 1,
			"children": [
			  {"username": "leaf.3.1", "shares": 100, "usage": 0},
			  {"username": "leaf.3.2", "shares": 10, "usage": 1}
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'run fairshare-emulate on small_no_tie' '
	flux account-fairshare-emulate \
		-i small_no_tie.json -o "{username},{fairshare}" > small_no_tie.test &&
	cat <<-EOF >small_no_tie.expected &&
	leaf.3.1,1.0
	leaf.3.2,0.857143
	leaf.2.1,0.714286
	leaf.2.2,0.571429
	leaf.1.3,0.428571
	leaf.1.1,0.285714
	leaf.1.2,0.142857
	EOF
	test_cmp small_no_tie.test small_no_tie.expected
'

test_expect_success 'create small_tie JSON input' '
	cat <<-EOF >small_tie.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 133,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 120,
			"children": [
			  {"username": "leaf.1.1", "shares": 10000, "usage": 100},
			  {"username": "leaf.1.2", "shares": 1000, "usage": 10},
			  {"username": "leaf.1.3", "shares": 100000, "usage": 10}
			]
		  },
		  {
			"bank": "account2",
			"shares": 100,
			"usage": 12,
			"children": [
			  {"username": "leaf.2.1", "shares": 10000, "usage": 10},
			  {"username": "leaf.2.2", "shares": 1000, "usage": 1},
			  {"username": "leaf.2.3", "shares": 100000, "usage": 1}
			]
		  },
		  {
			"bank": "account3",
			"shares": 10,
			"usage": 1,
			"children": [
			  {"username": "leaf.3.1", "shares": 100, "usage": 0},
			  {"username": "leaf.3.2", "shares": 10, "usage": 1}
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'run fairshare-emulate on small_tie' '
	flux account-fairshare-emulate \
		-i small_tie.json -o "{username},{fairshare}" > small_tie.test &&
	cat <<-EOF >small_tie.expected &&
	leaf.3.1,1.0
	leaf.3.2,0.875
	leaf.1.3,0.75
	leaf.2.3,0.75
	leaf.1.2,0.5
	leaf.2.2,0.5
	leaf.1.1,0.5
	leaf.2.1,0.5
	EOF
	test_cmp small_tie.test small_tie.expected
'

test_expect_success 'create small_tie_all JSON input' '
	cat <<-EOF >small_tie_all.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 1332,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 120,
			"children": [
			  {"username": "leaf.1.1", "shares": 10000, "usage": 100},
			  {"username": "leaf.1.2", "shares": 1000, "usage": 10},
			  {"username": "leaf.1.3", "shares": 100000, "usage": 10}
			]
		  },
		  {
			"bank": "account2",
			"shares": 100,
			"usage": 12,
			"children": [
			  {"username": "leaf.2.1", "shares": 10000, "usage": 10},
			  {"username": "leaf.2.2", "shares": 1000, "usage": 1},
			  {"username": "leaf.2.3", "shares": 100000, "usage": 1}
			]
		  },
		  {
			"bank": "account3",
			"shares": 10000,
			"usage": 1200,
			"children": [
			  {"username": "leaf.3.1", "shares": 10000, "usage": 1000},
			  {"username": "leaf.3.2", "shares": 1000, "usage": 100},
			  {"username": "leaf.3.3", "shares": 100000, "usage": 100}
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'run fairshare-emulate on small_tie_all' '
	flux account-fairshare-emulate \
		-i small_tie_all.json -o "{username},{fairshare}" > small_tie_all.test &&
	cat <<-EOF >small_tie_all.expected &&
	leaf.1.3,1.0
	leaf.2.3,1.0
	leaf.3.3,1.0
	leaf.1.2,0.666667
	leaf.2.2,0.666667
	leaf.3.2,0.666667
	leaf.1.1,0.666667
	leaf.2.1,0.666667
	leaf.3.1,0.666667
	EOF
	test_cmp small_tie_all.test small_tie_all.expected
'

test_expect_success 'fairshare-emulate on small_tie_all with JSON output' '
	flux account-fairshare-emulate \
		-i small_tie_all.json --json > small_tie_all_json.test &&
	test_cmp small_tie_all_json.test ${EXPECTED_FILES}/small_tie_all_json.expected
'

test_expect_success 'fairshare-emulate on small_tie_all with parsable output' '
	flux account-fairshare-emulate \
		-i small_tie_all.json -P > small_tie_all_parsable.test &&
	cat <<-EOF >small_tie_all_parsable.expected &&
	leaf.1.3|account1|100000|10|1.0
	leaf.2.3|account2|100000|1|1.0
	leaf.3.3|account3|100000|100|1.0
	leaf.1.2|account1|1000|10|0.666667
	leaf.2.2|account2|1000|1|0.666667
	leaf.3.2|account3|1000|100|0.666667
	leaf.1.1|account1|10000|100|0.666667
	leaf.2.1|account2|10000|10|0.666667
	leaf.3.1|account3|10000|1000|0.666667
	EOF
	test_cmp small_tie_all_parsable.test small_tie_all_parsable.expected
'

test_expect_success 'create single_user JSON input' '
	cat <<-EOF >single_user.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 100,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 100,
			"children": [
			  {"username": "only.user", "shares": 1000, "usage": 100}
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'single user in hierarchy gets fairshare 1.0' '
	flux account-fairshare-emulate \
		-i single_user.json -o "{username},{fairshare}" > single_user.test &&
	cat <<-EOF >single_user.expected &&
	only.user,1.0
	EOF
	test_cmp single_user.test single_user.expected
'

test_expect_success 'create empty_hierarchy JSON input' '
	cat <<-EOF >empty_hierarchy.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 0,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 0,
			"children": []
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'empty hierarchy produces no users message' '
	test_must_fail flux account-fairshare-emulate \
		-i empty_hierarchy.json > empty_hierarchy.err 2>&1 &&
	grep "no users found in input" empty_hierarchy.err
'

test_expect_success 'invalid format string raises error' '
	test_must_fail flux account-fairshare-emulate \
		-i single_user.json -o "{username},{invalid_field}" > bad_format.err 2>&1 &&
	grep "Invalid format string key" bad_format.err
'

test_expect_success 'create deeply_nested JSON input' '
	cat <<-EOF >deeply_nested.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 100,
		"children": [
		  {
			"bank": "level1",
			"shares": 1000,
			"usage": 100,
			"children": [
			  {
				"bank": "level2",
				"shares": 1000,
				"usage": 100,
				"children": [
				  {
					"bank": "level3",
					"shares": 1000,
					"usage": 100,
					"children": [
					  {"username": "deep.user1", "shares": 1000, "usage": 50},
					  {"username": "deep.user2", "shares": 1000, "usage": 50}
					]
				  }
				]
			  }
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'deeply nested hierarchy calculates correctly' '
	flux account-fairshare-emulate \
		-i deeply_nested.json -o "{username},{fairshare}" > deeply_nested.test &&
	cat <<-EOF >deeply_nested.expected &&
	deep.user1,1.0
	deep.user2,1.0
	EOF
	test_cmp deeply_nested.test deeply_nested.expected
'

test_expect_success 'create identical_weights JSON input' '
	cat <<-EOF >identical_weights.json
	{
	  "root": {
		"bank": "root",
		"shares": 1000,
		"usage": 300,
		"children": [
		  {
			"bank": "account1",
			"shares": 1000,
			"usage": 300,
			"children": [
			  {"username": "user.a", "shares": 1000, "usage": 100},
			  {"username": "user.b", "shares": 1000, "usage": 100},
			  {"username": "user.c", "shares": 1000, "usage": 100}
			]
		  }
		]
	  }
	}
	EOF
'

test_expect_success 'users with identical weights get equal fairshare' '
	flux account-fairshare-emulate \
		-i identical_weights.json -o "{username},{fairshare}" > identical_weights.test &&
	cat <<-EOF >identical_weights.expected &&
	user.a,1.0
	user.b,1.0
	user.c,1.0
	EOF
	test_cmp identical_weights.test identical_weights.expected
'

test_done
