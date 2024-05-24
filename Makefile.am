ACLOCAL_AMFLAGS = -I config

SUBDIRS = src etc doc t

EXTRA_DIST= \
	config/tap-driver.sh \
	config/tap-driver.py \
	DISCLAIMER.LLNS \
	README.md

CODE_COVERAGE_IGNORE_PATTERN = \
    "*/common/libtap/*" \
    "/usr/include/*" \
    "/usr/lib/*"
CODE_COVERAGE_LCOV_OPTIONS =
@CODE_COVERAGE_RULES@

dist_fluxrc1_SCRIPTS = \
    etc/01-flux-account-priority-update

export DEB_BUILD_OPTIONS ?= nocheck terse
deb: debian scripts/debbuild.sh
	@$(top_srcdir)/scripts/debbuild.sh $(abs_top_srcdir)

clean-local:
	@rm -rf debbuild
