AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

TESTS = data_writer_db_test01.t

check_PROGRAMS = $(TESTS)

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
       $(top_srcdir)/config/tap-driver.sh

data_writer_db_test01_t_SOURCES = \
	data_writer_db_test01.cpp
data_writer_db_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir) $(SQLITE_CFLAGS)
data_writer_db_test01_t_LDFLAGS = $(SQLITE_LIBS)
data_writer_db_test01_t_LDADD = \
    $(top_builddir)/src/fairness/weighted_tree/libweighted_tree.la \
    $(top_builddir)/src/common/libtap/libtap.la

AM_TESTS_ENVIRONMENT = \
	export ACCOUNTING_TEST_DB_DIR="$(abs_top_srcdir)/src/fairness/reader/test/accounting_db_data";

