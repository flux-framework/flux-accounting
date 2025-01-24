SUBDIRS = common bindings plugins

AM_CXXFLAGS = \
	$(WARNING_CXXFLAGS) \
	$(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS) $(SQLITE_LIBS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

noinst_LTLIBRARIES = fairness/libweighted_tree.la
noinst_HEADERS = \
	fairness/account/account.hpp \
	fairness/weighted_tree/weighted_tree.hpp \
	fairness/weighted_tree/weighted_walk.hpp \
	fairness/reader/data_reader_base.hpp \
	fairness/reader/data_reader_db.hpp \
	fairness/writer/data_writer_base.hpp \
	fairness/writer/data_writer_db.hpp \
	fairness/writer/data_writer_stdout.hpp \
	plugins/accounting.hpp \
	plugins/job.hpp \
	plugins/jj.hpp

fairness_libweighted_tree_la_SOURCES = \
	fairness/account/account.cpp \
	fairness/weighted_tree/weighted_tree.cpp \
	fairness/weighted_tree/weighted_walk.cpp \
	fairness/reader/data_reader_base.cpp \
	fairness/reader/data_reader_db.cpp \
	fairness/writer/data_writer_base.cpp \
	fairness/writer/data_writer_db.cpp \
	fairness/writer/data_writer_stdout.cpp \
	fairness/account/account.hpp \
	fairness/weighted_tree/weighted_tree.hpp \
	fairness/weighted_tree/weighted_walk.hpp \
	fairness/reader/data_reader_base.hpp \
	fairness/reader/data_reader_db.hpp \
	fairness/writer/data_writer_base.hpp \
	fairness/writer/data_writer_db.hpp \
	fairness/writer/data_writer_stdout.hpp

fairness_libweighted_tree_la_CXXFLAGS = \
	$(WARNING_CXXFLAGS) \
	$(CODE_COVERAGE_CFLAGS) \
	$(SQLITE_CFLAGS) \
	$(AM_CXXFLAGS)

TESTS = \
	weighted_tree_test01.t \
	data_reader_db_test01.t \
	data_writer_db_test01.t \
	accounting_test01.t
check_PROGRAMS = $(TESTS)

TEST_EXTENSIONS = .t
T_LOG_DRIVER = env AM_TAP_AWK='$(AWK)' $(SHELL) \
	   $(top_srcdir)/config/tap-driver.sh

AM_TESTS_ENVIRONMENT = \
	export ACCOUNTS_DATA_DIR="$(abs_top_srcdir)/src/fairness/weighted_tree/test/accounts_data"; \
	export ACCOUNTING_DB_DATA_DIR="$(abs_top_srcdir)/t/expected/test_dbs"; \
	export ACCOUNTING_TEST_DB_DIR="$(abs_top_srcdir)/src/fairness/reader/test/accounting_db_data";

weighted_tree_test01_t_SOURCES = \
	fairness/weighted_tree/test/weighted_tree_test01.cpp \
	fairness/weighted_tree/test/weighted_tree_load.cpp \
	fairness/weighted_tree/test/weighted_tree_load.hpp
weighted_tree_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir)
weighted_tree_test01_t_LDADD = \
	fairness/libweighted_tree.la \
	common/libtap/libtap.la

dist_check_DATA = \
	fairness/weighted_tree/test/accounts_data/minimal.csv \
	fairness/weighted_tree/test/accounts_data/small_no_tie.csv \
	fairness/weighted_tree/test/accounts_data/small_tie_all.csv \
	fairness/weighted_tree/test/accounts_data/small_tie.csv \
	fairness/weighted_tree/test/accounts_data/small_tie_diff_type.csv \
	fairness/weighted_tree/test/accounts_data/small_zero_shares.csv

data_reader_db_test01_t_SOURCES = \
	fairness/reader/test/data_reader_db_test01.cpp \
	fairness/reader/data_reader_db.cpp \
	fairness/reader/data_reader_db.hpp
data_reader_db_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir) $(SQLITE_CFLAGS)
data_reader_db_test01_t_LDFLAGS = $(SQLITE_LIBS)
data_reader_db_test01_t_LDADD = \
	fairness/libweighted_tree.la \
	common/libtap/libtap.la

data_writer_db_test01_t_SOURCES = \
	fairness/writer/test/data_writer_db_test01.cpp
data_writer_db_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir) $(SQLITE_CFLAGS)
data_writer_db_test01_t_LDFLAGS = $(SQLITE_LIBS)
data_writer_db_test01_t_LDADD = \
	fairness/libweighted_tree.la \
	common/libtap/libtap.la

accounting_test01_t_SOURCES = \
	plugins/test/accounting_test01.cpp \
	plugins/accounting.cpp \
	plugins/accounting.hpp
accounting_test01_t_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir) $(JANSSON_CFLAGS)
accounting_test01_t_LDADD = \
	common/libtap/libtap.la \
	$(JANSSON_LIBS)

noinst_PROGRAMS = \
	cmd/flux-account-update-fshare

cmd_flux_account_update_fshare_SOURCES = cmd/flux_account_update_fshare.cpp

cmd_flux_account_update_fshare_LDADD = \
	fairness/libweighted_tree.la

cmd_flux_account_update_fshare_CXXFLAGS = \
	$(WARNING_CXXFLAGS) \
	$(CODE_COVERAGE_CFLAGS) \
	$(AM_CXXFLAGS) \
	$(SQLITE_CFLAGS)

cmd_flux_account_update_fshare_LDFLAGS = $(SQLITE_LIBS)

dist_fluxcmd_SCRIPTS = \
	cmd/flux-account.py \
	cmd/flux-account-update-fshare \
	cmd/flux-account-priority-update.py \
	cmd/flux-account-update-db.py \
	cmd/flux-account-service.py \
	cmd/flux-account-fetch-job-records.py
