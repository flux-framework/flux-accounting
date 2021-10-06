AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS) $(SQLITE_LIBS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

SUBDIRS = .

noinst_PROGRAMS = flux-update-fshare
noinst_HEADERS = \
	../fairness/reader/data_reader_db.hpp \
	../fairness/writer/data_writer_db.hpp

flux_update_fshare_SOURCES = flux_update_fshare.cpp

flux_update_fshare_LDADD = \
    $(top_builddir)/src/fairness/weighted_tree/libweighted_tree.la

flux_update_fshare_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CFLAGS) \
    $(AM_CXXFLAGS) \
    $(SQLITE_CFLAGS)

flux_update_fshare_LDFLAGS = $(SQLITE_LIBS)

dist_fluxcmd_SCRIPTS = \
	flux-account.py \
	flux-update-fshare
