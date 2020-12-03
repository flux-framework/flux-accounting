ACLOCAL_AMFLAGS = -I config

SUBDIRS = src t

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
