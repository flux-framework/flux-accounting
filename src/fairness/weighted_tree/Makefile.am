AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS) $(SQLITE_LIBS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

SUBDIRS = . test

noinst_LTLIBRARIES = libweighted_tree.la
noinst_HEADERS = \
    ../account/account.hpp \
    weighted_tree.hpp \
    weighted_walk.hpp \
    ../reader/data_reader_base.hpp \
    ../reader/data_reader_db.hpp \
    ../writer/data_writer_base.hpp \
    ../writer/data_writer_db.hpp \
    ../writer/data_writer_stdout.hpp

libweighted_tree_la_SOURCES = \
    ../account/account.cpp \
    weighted_tree.cpp \
    weighted_walk.cpp \
    ../reader/data_reader_base.cpp \
    ../reader/data_reader_db.cpp \
    ../writer/data_writer_base.cpp \
    ../writer/data_writer_db.cpp \
    ../writer/data_writer_stdout.cpp \
    ../account/account.hpp \
    weighted_tree.hpp \
    weighted_walk.hpp \
    ../reader/data_reader_base.hpp \
    ../reader/data_reader_db.hpp \
    ../writer/data_writer_base.hpp \
    ../writer/data_writer_db.hpp \
    ../writer/data_writer_stdout.hpp

libweighted_tree_la_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CFLAGS) \
    $(SQLITE_CFLAGS) \
    $(AM_CXXFLAGS)
