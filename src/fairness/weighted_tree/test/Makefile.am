AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

TESTS = weighted_tree_test01.t
check_PROGRAMS = $(TESTS)

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
       $(top_srcdir)/config/tap-driver.sh

weighted_tree_test01_t_SOURCES = \
    weighted_tree_test01.cpp \
    weighted_tree_load.cpp \
    weighted_tree_load.hpp
weighted_tree_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir)
weighted_tree_test01_t_LDADD = \
    $(top_builddir)/src/fairness/weighted_tree/libweighted_tree.la \
    $(top_builddir)/src/common/libtap/libtap.la

dist_check_DATA = \
	accounts_data/minimal.csv \
	accounts_data/small_no_tie.csv \
	accounts_data/small_tie_all.csv \
	accounts_data/small_tie.csv \
	accounts_data/small_tie_diff_type.csv \
	accounts_data/small_zero_shares.csv

AM_TESTS_ENVIRONMENT = \
	export ACCOUNTS_DATA_DIR="$(abs_top_srcdir)/src/fairness/weighted_tree/test/accounts_data";
