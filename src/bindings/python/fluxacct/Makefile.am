SUBDIRS = database entities jobs policy formatting

fluxacctpydir = $(fluxpydir)

fluxacctpy_PYTHON = \
	__init__.py \
	config.py \
	util.py

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
