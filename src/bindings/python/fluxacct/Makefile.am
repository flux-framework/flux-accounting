acctpy_PYTHON = \
	__init__.py \
	accounting/user_subcommands.py \
	accounting/bank_subcommands.py \
	accounting/queue_subcommands.py \
	accounting/project_subcommands.py \
	accounting/job_usage_calculation.py \
	accounting/jobs_table_subcommands.py \
	accounting/db_info_subcommands.py \
	accounting/create_db.py \
	util/formatter.py \
	util/sql_util.py

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

clean-local:
	-rm -f *.pyc *.pyo
	-rm -rf __pycache__
