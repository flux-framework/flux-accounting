#!/bin/bash

test_description='test the flux account bash completion handler'

. `dirname $0`/sharness.sh

COMPLETION=${SHARNESS_TEST_SRCDIR}/../etc/bash-completion/account

test_expect_success 'completion snippet exists' '
	test -f ${COMPLETION}
'

# Drive the _flux_ext_account handler directly: set COMP_WORDS/COMP_CWORD as
# bash would, invoke it, and check COMPREPLY. This exercises our handler without
# needing flux-core completion installed or a running service.
run_completion_with_mode() {
	bash -c '
		mode=$1; shift
		source "$1"; shift
		logical_words=("$@")
		cur=${logical_words[${#logical_words[@]}-1]}
		prev=${logical_words[${#logical_words[@]}-2]}
		COMP_WORDS=()
		for word in "${logical_words[@]}"; do
			if [[ $word == *=* ]]; then
				COMP_WORDS+=("${word%%=*}" = "${word#*=}")
			else
				COMP_WORDS+=("$word")
			fi
		done
		COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
		if test "$mode" = with-bash-completion; then
			_get_comp_words_by_ref() {
				words=("${logical_words[@]}")
				cword=$((${#words[@]} - 1))
			}
		fi
		COMPREPLY=()
		_flux_ext_account account "$cur" "$prev"
		if ((${#COMPREPLY[@]})); then
			printf "%s\n" "${COMPREPLY[@]}"
		fi
	' _ "$@"
}

run_completion() {
	run_completion_with_mode with-bash-completion "${COMPLETION}" "$@"
}

run_completion_without_bash_completion() {
	run_completion_with_mode without-bash-completion "${COMPLETION}" "$@"
}

help_subcommands() {
	flux account --help |
	awk '
		/^positional arguments:/ { in_subcommands = 1; next }
		/^options:/ { in_subcommands = 0 }
		in_subcommands && /^    [[:alnum:]][[:alnum:]-]*[[:space:]]/ {
			print $1
		}
	'
}

# Only look at the option invocation (e.g. "-B, --bank=BANK"), not the help
# text that follows it, so hyphenated words like "comma-separated" in the
# help text are not mistaken for options.
help_options() {
	flux account "$1" --help |
	grep "^[[:space:]]*-" |
	sed -E "s/^[[:space:]]+//; s/[[:space:]]{2,}.*//" |
	grep -oE -- "(^|[ ,])--?[[:alnum:]][-[:alnum:]]*" |
	sed -E "s/^[ ,]//" |
	grep -vE -- "^(-h|--help)$"
}

test_expect_success 'snippet sources cleanly' '
	bash -c "source ${COMPLETION}"
'

test_expect_success 'snippet does not register a flux completion' '
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

test_expect_success 'completes the options of a subcommand' '
	run_completion flux account add-user -- > out.adduser &&
	grep -x -- --username out.adduser &&
	grep -x -- --max-sched-jobs out.adduser
'

test_expect_success 'completes options without bash-completion installed' '
	run_completion_without_bash_completion \
		flux account add-user -- > out.no-bash-completion &&
	grep -x -- --username out.no-bash-completion &&
	grep -x -- --max-sched-jobs out.no-bash-completion
'

test_expect_success 'filters options by current prefix' '
	run_completion flux account edit-queue --max-sched > out.sched &&
	grep -x -- --max-sched-jobs out.sched &&
	grep -x -- --max-sched-nodes-per-assoc out.sched &&
	test_must_fail grep -x -- --priority out.sched
'

test_expect_success 'unknown subcommands do not produce completion errors' '
	run_completion flux account foo.bar -- > out.unknown &&
	test_must_be_empty out.unknown &&
	run_completion flux account global "" > out.global &&
	test_must_be_empty out.global
'

test_expect_success 'does not offer options where a value is expected' '
	run_completion flux account add-user --bank "" > out.option-value &&
	test_must_be_empty out.option-value &&
	run_completion flux account pop-db -c "" > out.filename-value &&
	test_must_be_empty out.filename-value
'

test_expect_success 'completes -p and --path arguments with a filename' '
	touch somefile.db &&
	run_completion flux account -p "" > out.path-short &&
	grep -x somefile.db out.path-short &&
	run_completion flux account --path "" > out.path-long &&
	grep -x somefile.db out.path-long
'

test_expect_success '--path=VALUE before subcommand does not hide subcommand' '
	run_completion flux account --path=somefile.db add-user -- > out.path-subcmd &&
	grep -x -- --username out.path-subcmd &&
	grep -x -- --max-sched-jobs out.path-subcmd
'

test_expect_success 'completes --path=VALUE with a filename' '
	run_completion flux account --path=some > out.path-equals &&
	grep -x somefile.db out.path-equals
'

test_expect_success '--path=VALUE works without bash-completion installed' '
	run_completion_without_bash_completion \
		flux account --path=somefile.db add-user -- > out.no-bc-path-subcmd &&
	grep -x -- --username out.no-bc-path-subcmd &&
	run_completion_without_bash_completion \
		flux account --path=some > out.no-bc-path-equals &&
	grep -x somefile.db out.no-bc-path-equals &&
	run_completion_without_bash_completion \
		flux account --path= > out.no-bc-path-empty &&
	grep -x somefile.db out.no-bc-path-empty
'

test_expect_success 'completion lists match flux account help' '
	help_subcommands | sort -u > expected.subcommands &&
	run_completion flux account "" |
		grep -v "^-" |
		sort -u > actual.subcommands &&
	test_cmp expected.subcommands actual.subcommands &&
	for subcommand in $(cat expected.subcommands); do
		help_options "$subcommand" | sort -u > expected.options &&
		run_completion flux account "$subcommand" - |
			sed "/^$/d" |
			sort -u > actual.options &&
		test_cmp expected.options actual.options || return 1
	done
'

test_done
