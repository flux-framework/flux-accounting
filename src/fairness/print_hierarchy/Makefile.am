AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS) $(SQLITE_LIBS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

SUBDIRS = .

noinst_PROGRAMS = flux-shares
noinst_HEADERS = \
	../writer/data_writer_stdout.hpp

flux_shares_SOURCES = flux_shares.cpp

flux_shares_LDADD = \
    $(top_builddir)/src/fairness/weighted_tree/libweighted_tree.la

flux_shares_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CFLAGS) \
    $(AM_CXXFLAGS) \
    $(SQLITE_CFLAGS)

flux_shares_LDFLAGS = $(SQLITE_LIBS)

dist_fluxcmd_SCRIPTS = \
    flux-shares