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
