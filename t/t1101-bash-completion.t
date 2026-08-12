#!/bin/bash

test_description='test the flux account bash completion handler'

. `dirname $0`/sharness.sh

COMPLETION=${SHARNESS_TEST_SRCDIR}/../etc/flux-account-completion.bash

test_expect_success 'completion snippet exists' '
	test -f ${COMPLETION}
'

# Drive the _flux_account handler directly: set COMP_WORDS/COMP_CWORD as bash
# would, invoke it, and check COMPREPLY.  This exercises our handler without
# needing flux-core completion installed or a running service.
run_completion() {
	bash -c '
		source "$1"; shift
		COMP_WORDS=("$@")
		COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
		COMPREPLY=()
		_flux_account
		printf "%s\n" "${COMPREPLY[@]}"
	' _ "${COMPLETION}" "$@"
}

test_expect_success 'snippet sources cleanly' '
	bash -c "source ${COMPLETION}"
'

test_expect_success 'snippet leaves flux completion unchanged without flux-core helper' '
	test_must_fail bash -c '"'"'
		source "$1" &&
		complete -p flux
	'"'"' _ "${COMPLETION}"
'

test_expect_success 'completes subcommands when none given yet' '
	run_completion flux account "" > out.subcmds &&
	grep -x add-user out.subcmds &&
	grep -x view-usage-report out.subcmds &&
	grep -x list-configs out.subcmds
'

test_expect_success "completes a subcommand's options" '
	run_completion flux account add-user -- > out.adduser &&
	grep -x -- --username out.adduser &&
	grep -x -- --max-sched-jobs out.adduser
'

test_expect_success 'filters options by current prefix' '
	run_completion flux account edit-queue --max-sched > out.sched &&
	grep -x -- --max-sched-jobs out.sched &&
	grep -x -- --max-sched-nodes-per-assoc out.sched &&
	test_must_fail grep -x -- --priority out.sched
'

test_expect_success 'completes --path argument with a filename' '
	touch somefile.db &&
	run_completion flux account -p "" > out.path &&
	grep -x somefile.db out.path
'

test_expect_success 'delegates non-account commands to flux-core completion' '
	bash -c '"'"'
		_flux_core() { COMPREPLY=(delegated); }
		source "$1"
		complete -p flux | grep -F "_flux_account_wrap" &&
		COMP_WORDS=(flux job "")
		COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
		COMPREPLY=()
		_flux_account_wrap
		printf "%s\n" "${COMPREPLY[@]}"
	'"'"' _ "${COMPLETION}" > out.wrap &&
	grep -x delegated out.wrap
'

test_expect_success 'registers wrapper via bash-completion loader' '
	bash -c '"'"'
		_completion_loader() {
			_flux_core() { COMPREPLY=(loaded); }
		}
		source "$1"
		complete -p flux | grep -F "_flux_account_wrap" &&
		COMP_WORDS=(flux queue "")
		COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
		COMPREPLY=()
		_flux_account_wrap
		printf "%s\n" "${COMPREPLY[@]}"
	'"'"' _ "${COMPLETION}" > out.loader &&
	grep -x loaded out.loader
'

test_done
