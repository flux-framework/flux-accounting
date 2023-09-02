# This list is included in both TESTS and dist_check_SCRIPTS.
TESTSCRIPTS = \
	t0000-sharness.t \
	t1000-print-hierarchy.t \
	t1001-mf-priority-basic.t \
	t1002-mf-priority-small-no-tie.t \
	t1003-mf-priority-small-tie.t \
	t1004-mf-priority-small-tie-all.t \
	t1005-max-jobs-limits.t \
	t1006-update-fshare.t \
	t1007-flux-account-users.t \
	t1008-mf-priority-update.t \
	t1009-pop-db.t \
	t1010-update-usage.t \
	t1011-job-archive-interface.t \
	t1012-mf-priority-load.t \
	t1013-mf-priority-queues.t \
	t1014-mf-priority-dne.t \
	t1015-mf-priority-urgency.t \
	t1016-export-db.t \
	t1017-update-db.t \
	t1018-mf-priority-disable-entry.t \
	t1019-mf-priority-info-fetch.t \
	t1020-mf-priority-issue262.t \
	t1021-mf-priority-issue332.t \
	t1022-mf-priority-issue346.t \
	t1023-flux-account-banks.t \
	t1024-flux-account-queues.t \
	t1025-flux-account-projects.t \
	t1026-flux-account-perms.t \
	t5000-valgrind.t \
	python/t1000-example.py

dist_check_SCRIPTS = \
	$(TESTSCRIPTS) \
	pycotap \
	scripts \
	valgrind/valgrind-workload.sh \
	valgrind/workload.d/job

dist_check_DATA = \
	valgrind/valgrind.supp

TESTS = $(TESTSCRIPTS)

EXTRA_DIST= \
	aggregate-results.sh \
	sharness.sh \
	sharness.d \
	rc \
	expected/print_hierarchy/custom_small_tie_parsable.txt \
	expected/print_hierarchy/help_message.txt \
	expected/print_hierarchy/out_of_insert_order.txt \
	expected/print_hierarchy/small_no_tie_parsable.txt \
	expected/print_hierarchy/small_no_tie.txt \
	expected/print_hierarchy/small_tie_all_parsable.txt \
	expected/print_hierarchy/small_tie_all.txt \
	expected/print_hierarchy/small_tie_parsable.txt \
	expected/print_hierarchy/small_tie.txt \
	expected/print_hierarchy/before_delete.expected \
	expected/print_hierarchy/after_delete.expected \
	expected/print_hierarchy/after_bank_delete.expected \
	expected/print_hierarchy/before_parent_bank_change.expected \
	expected/print_hierarchy/after_parent_bank_change.expected \
	expected/update_fshare/post_fshare_update.expected \
	expected/update_fshare/pre_fshare_update.expected \
	expected/test_dbs/out_of_insert_order.db \
	expected/test_dbs/small_no_tie.db \
	expected/test_dbs/small_tie_all.db \
	expected/test_dbs/small_tie_zero_shares.db \
	expected/test_dbs/small_tie.db \
	expected/test_dbs/FluxAccountingv0-10-0.db \
	expected/test_dbs/FluxAccountingv0-11-0.db \
	expected/test_dbs/FluxAccountingv0-12-0.db \
	expected/test_dbs/FluxAccountingv0-13-0.db \
	expected/test_dbs/FluxAccountingv0-14-0.db \
	expected/test_dbs/FluxAccountingv0-15-0.db \
	expected/test_dbs/FluxAccountingv0-16-0.db \
	expected/test_dbs/FluxAccountingv0-17-0.db \
	expected/test_dbs/FluxAccountingv0-18-0.db \
	expected/test_dbs/FluxAccountingv0-19-0.db \
	expected/test_dbs/FluxAccountingv0-25-0.db \
	expected/flux_account/A_bank.expected \
	expected/flux_account/D_bank.expected \
	expected/flux_account/full_hierarchy.expected \
	expected/flux_account/root_bank.expected \
	expected/flux_account/deleted_user.expected \
	expected/flux_account/deleted_bank.expected \
	expected/flux_account/F_bank_tree.expected \
	expected/flux_account/F_bank_users.expected \
	expected/pop_db/db_hierarchy_base.expected \
	expected/pop_db/db_hierarchy_new_users.expected \
	expected/job_usage/pre_update.expected \
	expected/job_usage/post_update1.expected \
	expected/job_usage/post_update2.expected \
	expected/plugin_state/internal_state_1.expected \
	expected/plugin_state/internal_state_3.expected

clean-local:
	rm -fr trash-directory.* test-results .prove *.broker.log */*.broker.log *.output

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/bindings/python/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
        $(top_srcdir)/config/tap-driver.sh
