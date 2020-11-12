fluxpy_PYTHON = \
	__init__.py \
	accounting_cli_functions.py \
	job_archive_interface.py \
	create_db.py

dist_noinst_SCRIPTS = \
	print_hierarchy.py

dist_fluxcmd_SCRIPTS = \
	flux-account.py

clean-local:
	-rm -f *.pyc *.pyo
	-rm -rf __pycache__

install-data-hook:
	$(AM_V_at)echo Linking python modules in non-standard location... && \
	  $(INSTALL) -d -m 0755 "$(DESTDIR)$(fluxpylinkdir)" && \
	  target=$(fluxpydir) && \
	  f=$${target##*/} && \
	  cd "$(DESTDIR)$(fluxpylinkdir)" && \
	  rm -f $$f && \
	  $(LN_S) $$target .

uninstall-local:
	$(AM_V_at)target=$(fluxpydir) && f=$${target##*/} && \
	  echo "Removing $(fluxpylinkdir)/$$f" && \
	  rm -rf $(fluxpylinkdir)/$$f

TESTSCRIPTS = \
	test/test_bank_subcommands.py \
	test/test_create_db.py \
	test/test_example.py \
	test/test_job_archive_interface.py \
	test/test_user_subcommands.py

dist_check_SCRIPTS = \
	$(TESTSCRIPTS)

TESTS = $(TESTSCRIPTS)

AM_TESTS_ENVIRONMENT = \
	export PYTHONPATH="$(abs_top_srcdir)/src/:$(abs_top_srcdir)/t/pycotap:$(PYTHON_SITE_PKG):$$PYTHONPATH";\
	export PYTHON="${PYTHON}";

TEST_EXTENSIONS = .py
PY_LOG_DRIVER = $(PYTHON) $(top_srcdir)/config/tap-driver.py
