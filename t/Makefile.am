# This list is included in both TESTS and dist_check_SCRIPTS.
TESTSCRIPTS = \
	t0000-sharness.t \
	t1000-print-hierarchy.t

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
	export PYTHONPATH="$(abs_top_srcdir)/src/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";
