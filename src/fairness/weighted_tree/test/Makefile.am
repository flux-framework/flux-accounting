AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

TESTS = weighted_tree_test01

check_PROGRAMS = $(TESTS)
weighted_tree_test01_SOURCES = \
    weighted_tree_test01.cpp \
    weighted_tree_load.cpp \
    weighted_tree_load.hpp
weighted_tree_test01_CXXFLAGS = $(AM_CXXFLAGS) -I$(top_srcdir)
weighted_tree_test01_LDADD = \
    $(top_builddir)/src/fairness/weighted_tree/libweighted_tree.la \
    $(top_builddir)/src/common/libtap/libtap.la
