AM_LDFLAGS = -module -shared $(CODE_COVERAGE_LDFLAGS)

AM_CPPFLAGS = -I$(top_srcdir) $(FLUX_CORE_CFLAGS)

AM_CXXFLAGS = $(CODE_COVERAGE_CXXFLAGS) -fPIC -shared

jobtapdir = \
  $(fluxlibdir)/job-manager/plugins/

jobtap_LTLIBRARIES = mf_priority.la
mf_priority_la_SOURCES = mf_priority.cpp accounting.cpp jj.cpp job.cpp
mf_priority_la_CPPFLAGS = -I$(top_srcdir)/src/plugins
mf_priority_la_LDFLAGS = $(fluxplugin_ldflags) -module
