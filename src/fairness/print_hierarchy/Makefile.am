AM_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CXXFLAGS)

AM_LDFLAGS = $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = $(FLUX_CORE_CFLAGS)

SUBDIRS = .

noinst_PROGRAMS = print_hierarchy

print_hierarchy_SOURCES = \
    print_hierarchy.cpp

print_hierarchy_CXXFLAGS = \
    $(WARNING_CXXFLAGS) \
    $(CODE_COVERAGE_CFLAGS) \
    $(AM_CXXFLAGS) \
                $(SQLITE_CFLAGS)

print_hierarchy_LDFLAGS = \
                $(SQLITE_LIBS)

TESTS = test-print-hierarchy.sh
