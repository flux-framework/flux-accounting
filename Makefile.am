ACLOCAL_AMFLAGS = -I config

SUBDIRS = src

EXTRA_DIST= \
	config/tap-driver.sh \
	DISCLAIMER.LLNS \
	README.md

CODE_COVERAGE_IGNORE_PATTERN = \
    "*/common/libtap/*" \
    "/usr/include/*" \
    "/usr/lib/*"
CODE_COVERAGE_LCOV_OPTIONS =
@CODE_COVERAGE_RULES@

