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
	t1007-flux-account.t \
	t1008-mf-priority-update.t

dist_check_SCRIPTS = \
	$(TESTSCRIPTS) \
	pycotap \
	scripts

TESTS = $(TESTSCRIPTS)

EXTRA_DIST= \
	aggregate-results.sh \
	sharness.sh \
	sharness.d \
	rc \
	expected/custom_small_tie_parsable.txt \
	expected/help_message.txt \
	expected/out_of_insert_order.txt \
	expected/post_fshare_update.expected \
	expected/pre_fshare_update.expected \
	expected/small_no_tie_parsable.txt \
	expected/small_no_tie.txt \
	expected/small_tie_all_parsable.txt \
	expected/small_tie_all.txt \
	expected/small_tie_parsable.txt \
	expected/small_tie.txt \
	expected/test_dbs/out_of_insert_order.db \
	expected/test_dbs/small_no_tie.db \
	expected/test_dbs/small_tie_all.db \
	expected/test_dbs/small_tie_zero_shares.db \
	expected/test_dbs/small_tie.db

clean-local:
	rm -fr trash-directory.* test-results .prove *.broker.log */*.broker.log *.output

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/bindings/python/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
        $(top_srcdir)/config/tap-driver.sh
