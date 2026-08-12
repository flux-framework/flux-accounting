#!/bin/bash
#
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
#
# Bash completion for `flux account` subcommands.
#
# flux-core owns the `flux` completion (`complete -F _flux_core flux`) and
# provides no hook for add-on subcommands, so this file wraps it: it intercepts
# `flux account ...` and delegates every other command back to `_flux_core`.
#
# To avoid clobbering existing `flux` completion, only register the wrapper
# once `_flux_core` is already loaded or can be loaded through the
# bash-completion `_completion_loader` helper.
#
# The subcommand and option lists below are hand-maintained mirrors of the
# argparse definitions in src/cmd/flux-account.py -- keep them in sync when a
# subcommand or option is added, removed, or renamed.

# Complete the `account` subcommand only; assumes COMP_WORDS/COMP_CWORD are set.
_flux_account()
{
    local subcmds="add-bank add-config add-project add-queue add-user \
bank-info clear-usage create-db delete-bank delete-config delete-project \
delete-queue delete-user edit-all-users edit-bank edit-config edit-factor \
edit-queue edit-user export-db export-json jobs list-banks list-configs \
list-factors list-projects list-queues list-users pop-db reset-factors \
scrub-old-jobs show-usage sync-userids update-usage view-bank view-config \
view-factor view-job-records view-project view-queue view-usage-report \
view-user"

    # options that precede the subcommand: `flux account -p PATH <subcmd>`
    local global_OPTS="-p --path"

    # per-subcommand options (name with '-' replaced by '_')
    local view_user_OPTS="--parsable --list-banks -o --format --fields -J --job-usage"
    local list_users_OPTS="-f --fields -j --json -o --format --active -B --bank --shares --max-running-jobs --max-active-jobs -N --max-nodes -c --max-cores -q --queues -P --projects --default-project --max-sched-jobs"
    local add_user_OPTS="-u --username -i --userid -B --bank --shares --fairshare --max-running-jobs --max-active-jobs -N --max-nodes -c --max-cores -q --queues -P --projects --default-project --max-sched-jobs"
    local delete_user_OPTS="--force"
    local edit_user_OPTS="-B --bank -i --userid --default-bank --shares --fairshare --max-running-jobs --max-active-jobs -N --max-nodes -c --max-cores -q --queues --add-queue --delete-queue -P --projects --default-project --max-sched-jobs"
    local edit_all_users_OPTS="--bank --default-bank --shares --fairshare --max-running-jobs --max-active-jobs --max-nodes --max-cores --queues --projects --default-project --max-sched-jobs"
    local view_job_records_OPTS="-u --user -j --jobid -a --after-start-time -b --before-end-time --project -B --bank -d --requested-duration -e --actual-duration -D --duration-delta -o --format"
    local create_db_OPTS="--priority-usage-reset-period --priority-decay-half-life --decay-factor"
    local add_bank_OPTS="--parent-bank --priority --ignore-older-than"
    local view_bank_OPTS="-t --tree -u --users -P --parsable --fields -o --format -c --concise -A --active"
    local delete_bank_OPTS="--force"
    local edit_bank_OPTS="--shares --parent-bank --priority --ignore-older-than"
    local list_banks_OPTS="--inactive --fields --json -o --format"
    local bank_info_OPTS="-v --verbose -P --parsable -n --noheader -x --exclude -t --tree -T --tree-no-users -r --to-root -u --user"
    local update_usage_OPTS=""
    local add_queue_OPTS="--min-nodes-per-job -N --max-nodes-per-job -t --max-time-per-job -P --priority --max-running-jobs --max-nodes-per-assoc --max-sched-jobs -msn --max-sched-nodes-per-assoc -msc --max-sched-cores-per-assoc"
    local view_queue_OPTS="--parsable -o --format"
    local edit_queue_OPTS="--min-nodes-per-job -N --max-nodes-per-job -t --max-time-per-job -P --priority --max-running-jobs --max-nodes-per-assoc --max-sched-jobs -msn --max-sched-nodes-per-assoc -msc --max-sched-cores-per-assoc"
    local delete_queue_OPTS=""
    local add_project_OPTS=""
    local view_project_OPTS="--parsable -o --format"
    local delete_project_OPTS=""
    local list_projects_OPTS="--fields --json -o --format"
    local scrub_old_jobs_OPTS=""
    local export_db_OPTS="-F --fairshare-emulate"
    local pop_db_OPTS="-c --csv-file -f --fields"
    local list_queues_OPTS="--fields --json -o --format"
    local view_factor_OPTS="--json -o --format"
    local edit_factor_OPTS="--factor --weight"
    local list_factors_OPTS="--fields --json -o --format"
    local reset_factors_OPTS=""
    local jobs_OPTS="--bank --queue -o --format -f --filter -c --count --since -j --jobids -v --verbose"
    local show_usage_OPTS="-n --limit"
    local sync_userids_OPTS=""
    local export_json_OPTS=""
    local view_usage_report_OPTS="-s --start -e --end -u --username -b --bank -r --report-type -t --time-unit -S --job-size-bins"
    local clear_usage_OPTS="--ignore-older-than"
    local add_config_OPTS=""
    local view_config_OPTS="--json -o --format"
    local edit_config_OPTS=""
    local delete_config_OPTS=""
    local list_configs_OPTS="--fields --json -o --format"

    local cur prev
    if declare -F _get_comp_words_by_ref >/dev/null 2>&1; then
        _get_comp_words_by_ref -n = cur prev
    else
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    fi

    # complete the argument to the global --path/-p option with filenames
    case "$prev" in
        -p | --path)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
    esac

    # locate the account subcommand: first non-option word after "account"
    local i subcmd="" seen_account=f
    for ((i = 0; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        if [[ "$seen_account" == f ]]; then
            [[ "$w" == "account" ]] && seen_account=t
            continue
        fi
        case "$w" in
            -p | --path) ((i++)) ;;   # skip its value
            -*) ;;
            *) subcmd="$w"; break ;;
        esac
    done

    if [[ -z "$subcmd" ]]; then
        COMPREPLY=( $(compgen -W "${subcmds} ${global_OPTS}" -- "$cur") )
        return 0
    fi

    local var="${subcmd//-/_}_OPTS"
    COMPREPLY=( $(compgen -W "${!var}" -- "$cur") )
    return 0
}

# Wrap flux-core's `_flux_core` completion: handle `account`, delegate the rest.
_flux_account_wrap()
{
    # first non-option word after "flux" is the command
    local i cmd=""
    for ((i = 1; i < COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            -*) ;;
            *) cmd="${COMP_WORDS[i]}"; break ;;
        esac
    done

    if [[ "$cmd" == "account" ]]; then
        _flux_account
    elif declare -F _flux_core >/dev/null 2>&1; then
        _flux_core "$@"
    fi
    return 0
}

_flux_account_enable()
{
    if ! declare -F _flux_core >/dev/null 2>&1 \
       && declare -F _completion_loader >/dev/null 2>&1; then
        _completion_loader flux
    fi

    if declare -F _flux_core >/dev/null 2>&1; then
        complete -F _flux_account_wrap flux
    fi
}

_flux_account_enable
