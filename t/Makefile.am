# This list is included in both TESTS and dist_check_SCRIPTS.
TESTSCRIPTS = \
	t0000-sharness.t \
	t1000-print-hierarchy.t \
	t1001-mf-priority-basic.t \
	t1002-mf-priority-small-no-tie.t \
	t1003-mf-priority-small-tie.t \
	t1004-mf-priority-small-tie-all.t

dist_check_SCRIPTS = \
	$(TESTSCRIPTS) \
	pycotap \
	scripts

TESTS = $(TESTSCRIPTS)

EXTRA_DIST= \
	aggregate-results.sh \
	sharness.sh \
	sharness.d

clean-local:
	rm -fr trash-directory.* test-results .prove *.broker.log */*.broker.log *.output

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/bindings/python/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
        $(top_srcdir)/config/tap-driver.sh
