AM_LDFLAGS = \
	$(CODE_COVERAGE_LIBS)

# This list is included in both TESTS and dist_check_SCRIPTS.
TESTSCRIPTS = \
	t0000-sharness.t \
	t1001-mf-priority-basic.t \
	t1002-mf-priority-small-no-tie.t \
	t1003-mf-priority-small-tie.t \
	t1004-mf-priority-small-tie-all.t \
	t1005-max-jobs-limits.t \
	t1006-update-fshare.t \
	t1007-flux-account-users.t \
	t1008-mf-priority-update.t \
	t1009-pop-db.t \
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
	t1027-mf-priority-issue376.t \
	t1028-mf-priority-issue385.t \
	t1029-mf-priority-default-bank.t \
	t1030-mf-priority-update-queue.t \
	t1031-mf-priority-issue406.t \
	t1032-mf-priority-update-bank.t \
	t1033-mf-priority-update-job.t \
	t1034-mf-priority-config.t \
	t1035-flux-account-scrub-old-jobs.t \
	t1036-hierarchy-small-no-tie-db.t \
	t1037-hierarchy-small-tie-db.t \
	t1038-hierarchy-small-tie-all-db.t \
	t1039-issue476.t \
	t1040-mf-priority-projects.t \
	t1041-view-jobs-by-project.t \
	t1042-issue508.t \
	t1043-view-jobs-by-bank.t \
	t1044-mf-priority-resource-limits.t \
	t1045-issue478.t \
	t1046-issue565.t \
	t1047-issue564.t \
	t1048-issue575.t \
	t1049-issue580.t \
	t1050-mf-priority-update-on-reload.t \
	t1051-list-users.t \
	t1052-mf-priority-queue-limits.t \
	t1053-issue631.t \
	t1054-mf-priority-bank-priorities.t \
	t1055-flux-account-priorities.t \
	t1056-mf-priority-urgency-factor.t \
	t1057-flux-account-jobs.t \
	t1058-flux-account-visuals.t \
	t1059-issue685.t \
	t1060-mf-priority-queue-usage.t \
	t1061-flux-account-edit-all-users.t \
	t1062-mf-priority-queue-resource-limits.t \
	t1063-issue709.t \
	t1064-store-job-duration.t \
	t1065-view-jobs-by-duration.t \
	t1066-view-bank-concise.t \
	t1067-mf-priority-issue733.t \
	t1068-mf-priority-queues-projects-query.t \
	t1069-duration-delta.t \
	t1070-issue749.t \
	t1071-issue754.t \
	t1072-sync-uids.t \
	t1073-mf-priority-init-basic.t \
	t5000-valgrind.t \
	python/t1000-example.py \
	python/t1001_db.py \
	python/t1002_user_cmds.py \
	python/t1003_bank_cmds.py \
	python/t1004_queue_cmds.py \
	python/t1005_project_cmds.py \
	python/t1006_job_archive.py \
	python/t1007_formatter.py \
	python/t1008_banks_output.py \
	python/t1009_users_output.py \
	python/t1010_issue631.py \
	python/t1011_priorities.py \
	python/t1012_visuals.py

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
	expected/flux_account/E_bank.expected \
	expected/flux_account/full_hierarchy.expected \
	expected/flux_account/root_bank.expected \
	expected/flux_account/deleted_user.expected \
	expected/flux_account/deleted_bank.expected \
	expected/flux_account/F_bank_tree.expected \
	expected/flux_account/F_bank_users.expected \
	expected/pop_db/db_hierarchy_base.expected \
	expected/pop_db/db_hierarchy_new_users.expected \
	expected/sample_payloads/same_fairshare.json \
	expected/sample_payloads/small_no_tie.json \
	expected/sample_payloads/small_tie_all.json \
	expected/sample_payloads/small_tie.json

clean-local:
	rm -fr trash-directory.* test-results .prove *.broker.log */*.broker.log *.output

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/bindings/python/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
        $(top_srcdir)/config/tap-driver.sh
