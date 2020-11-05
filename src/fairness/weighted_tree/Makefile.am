AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

SUBDIRS = . test

noinst_LTLIBRARIES = libweighted_tree.la
noinst_HEADERS = ../account/account.hpp weighted_tree.hpp weighted_walk.hpp

libweighted_tree_la_SOURCES = \
    ../account/account.cpp \
    weighted_tree.cpp \
    weighted_walk.cpp \
    ../account/account.hpp \
    weighted_tree.hpp \
    weighted_walk.hpp

libweighted_tree_la_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CFLAGS) \
    $(AM_CXXFLAGS)

