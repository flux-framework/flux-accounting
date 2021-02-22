#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])
AC_INIT([flux-accounting],
        m4_esyscmd([git describe --always | awk '/.*/ {sub(/^v/, ""); printf "%s",$1; exit}']))
AC_CONFIG_AUX_DIR([config])
AC_CONFIG_MACRO_DIR([config])
AC_CONFIG_SRCDIR([NEWS])

AM_INIT_AUTOMAKE([subdir-objects tar-ustar filename-length-max=256 foreign])
AM_SILENT_RULES([yes])
AM_CONFIG_HEADER([config.h])
AM_MAINTAINER_MODE([enable])

LT_INIT([dlopen])

AC_PREFIX_PROGRAM([flux])

##
# Initialize pkg-config for PKG_CHECK_MODULES to avoid conditional issues
##
PKG_PROG_PKG_CONFIG

# Checks for programs.
AC_DEFINE([_GNU_SOURCE], 1,
          [Define _GNU_SOURCE so that we get all necessary prototypes])
AC_PROG_CC_C99
AC_PROG_CXX
AX_CXX_COMPILE_STDCXX([11], [noext], [mandatory])
AC_PROG_LN_S
AC_PROG_MAKE_SET
AM_PROG_CC_C_O
AX_CODE_COVERAGE
PKG_CHECK_MODULES([SQLITE], [sqlite3], [], [])

if test "$GCC" = yes; then
  WARNING_CFLAGS="-Wall -Werror -Werror=missing-field-initializers -Wno-error=deprecated-declarations"
  AC_SUBST([WARNING_CFLAGS])
fi
if test "$GXX" = "yes"; then
  WARNING_CXXFLAGS=$WARNING_CFLAGS
  AC_SUBST([WARNING_CXXFLAGS])
fi

AX_FLUX_CORE

#  Set PYTHON_VERSION to FLUX_PYTHON_VERSION here
PYTHON_VERSION=${PYTHON_VERSION:-$FLUX_PYTHON_VERSION}
AX_PYTHON_DEVEL([>='3.6'])

AM_PATH_PYTHON([$ac_python_version])
if test "X$PYTHON" = "X"; then
  AC_MSG_ERROR([could not find python])
fi

AC_SUBST(PYTHON_LIBRARY, lib${ac_python_library}.so)
AC_DEFINE_UNQUOTED([PYTHON_INTERPRETER], ["$PYTHON"], [The python interpreter flux is configured with])
AC_SUBST(PYTHON)

AM_CHECK_PYMOD(pandas,
               [StrictVersion(pandas.__version__) >= StrictVersion('0.24.1')],
               ,
               [AC_MSG_ERROR([could not find python module pandas, version 0.24.1+ required])]
               )

#
# Project directories
#
AS_VAR_SET(fluxcmddir, $libexecdir/flux/cmd)
AC_SUBST(fluxcmddir)

AS_VAR_SET(fluxlibdir, $libdir/flux)
AC_SUBST(fluxlibdir)

AS_VAR_SET(fluxmoddir, $libdir/flux/modules)
AC_SUBST(fluxmoddir)

AS_VAR_SET(fluxrc1dir, $sysconfdir/flux/rc1.d)
AC_SUBST(fluxrc1dir)

AS_VAR_SET(fluxrc3dir, $sysconfdir/flux/rc3.d)
AC_SUBST(fluxrc3dir)

AS_VAR_SET(fluxrc1dir, $sysconfdir/flux/rc1.d)
AC_SUBST(fluxrc1dir)

AS_VAR_SET(fluxrc3dir, $sysconfdir/flux/rc3.d)
AC_SUBST(fluxrc3dir)

AS_VAR_SET(fluxpydir, $pyexecdir/fluxacct)
AC_SUBST(fluxpydir)
AS_VAR_SET(acctpydir, $fluxpydir/accounting)
AC_SUBST(acctpydir)

adl_RECURSIVE_EVAL([$localstatedir], acct_db_path)
AS_VAR_SET(acct_db_path, $acct_db_path)
AC_SUBST(acct_db_path)

AC_CONFIG_FILES([Makefile
  src/Makefile
  src/common/Makefile
  src/common/libtap/Makefile
  src/fairness/Makefile
  src/fairness/weighted_tree/Makefile
  src/fairness/weighted_tree/test/Makefile
  src/fairness/reader/Makefile
  src/fairness/reader/test/Makefile
  src/fairness/print_hierarchy/Makefile
  src/bindings/Makefile
  src/bindings/python/Makefile
  src/bindings/python/fluxacct/Makefile
  src/bindings/python/fluxacct/accounting/Makefile
  src/bindings/python/fluxacct/accounting/__init__.py
  src/cmd/Makefile
  t/Makefile
  ])
AC_OUTPUT

echo "
  $PACKAGE_NAME version $PACKAGE_VERSION
  Prefix...........: $prefix
  Debug Build......: $debug
  C Compiler.......: $CC
  C++ Compiler.....: $CXX
  CFLAGS...........: $CFLAGS
  CPPFLAGS.......... $CPPFLAGS
  CXXFLAGS.......... $CXXFLAGS
  FLUX.............: $FLUX
  FLUX_VERSION.....: $($FLUX version | sed -n 's/libflux-core:\t*//p')
  FLUX_CORE_CFLAGS.: $FLUX_CORE_CFLAGS
  FLUX_CORE_LIBS...: $FLUX_CORE_LIBS
  LIBFLUX_VERSION..: $LIBFLUX_VERSION
  FLUX_PREFIX......: $FLUX_PREFIX
  LDFLAGS..........: $LDFLAGS
  LIBS.............: $LIBS
  Linker...........: $LD
  PYTHON...........: $PYTHON
"
