acctpy_PYTHON = \
	__init__.py \
	user_subcommands.py \
	bank_subcommands.py \
	queue_subcommands.py \
	plugin_factor_subcommands.py \
	job_archive_interface.py \
	create_db.py

clean-local:
	-rm -f *.pyc *.pyo
	-rm -rf __pycache__

TESTSCRIPTS = \
	test/test_bank_subcommands.py \
	test/test_create_db.py \
	test/test_example.py \
	test/test_job_archive_interface.py \
	test/test_user_subcommands.py \
	test/test_queue_subcommands.py \
	test/test_plugin_factor_subcommands.py

dist_check_SCRIPTS = \
	$(TESTSCRIPTS)

TESTS = $(TESTSCRIPTS)

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/bindings/python/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .py
PY_LOG_DRIVER = $(PYTHON) $(top_srcdir)/config/tap-driver.py
