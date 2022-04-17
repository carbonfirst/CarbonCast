## This is a automake file, part of Unidata's netCDF package.
# Copyright 2005, see the COPYRIGHT file for more information.
# This file builds and runs the ncdump program.

# $Id: Makefile.am,v 1.83 2008/05/23 16:26:24 ed Exp $

LDADD = -lm

CLEANFILES = test0.nc tst_small.nc tst_small.cdl test1.cdl test1.nc	\
test2.cdl ctest1.cdl ctest.c ctest64.c ctest0.nc ctest0_64.nc c1.cdl	\
ctest1_64.cdl c0.nc tst_solar_1.cdl small.nc small2.nc c0tmp.nc		\
tst_solar_2.cdl tst_ncml.nc c1.ncml

# These tests are run for both netCDF-4 and non-neCDF-4 builds.
TESTPROGRAMS = rewrite-scalar ctest ctest64 ncdump
check_PROGRAMS = $(TESTPROGRAMS)
TESTS = run_tests.sh tst_64bit.sh ctest ctest64 tst_output.sh	\
tst_lengths.sh

# Always include this, even if not used
tst_utf8_SOURCES = tst_utf8.c

CLEANFILES += utf8.cdl utf8_64.cdl utf8.nc utf8_64.nc \
              tst_utf8.nc tst_utf8.cdl
check_PROGRAMS += tst_utf8
TESTS += tst_utf8
TESTS += run_utf8_tests.sh

AM_CPPFLAGS = -I$(top_srcdir)/nc_test 

# Is the user building netCDF-4?
if USE_NETCDF4

AM_LDFLAGS =

# Link to netCDF-4 and hdf libs.
LDADD += ../libsrc4/libnetcdf.la -lhdf5_hl -lhdf5

# Find netcdf.h in libsrc4.
AM_CPPFLAGS += -I../libsrc4 -I$(top_srcdir)/libsrc4

# If the user specified a root for HDF5, use it.
if USE_HDF5_DIR
AM_CPPFLAGS += -I@HDF5DIR@/include
AM_LDFLAGS += -L@HDF5DIR@/lib
endif

# If the user specified a root location for ZLIB, use it.
if USE_ZLIB_DIR
AM_CPPFLAGS += -I@ZLIBDIR@/include
AM_LDFLAGS += -L@ZLIBDIR@/lib
endif

# If the user specified a root location for SZLIB, use it.
if USE_SZLIB_DIR
AM_CPPFLAGS += -I@SZLIBDIR@/include
AM_LDFLAGS += -L@SZLIBDIR@/lib
endif

# NetCDF-4 has some extra tests.
check_PROGRAMS += tst_create_files tst_h_rdc0 tst_group_data		\
	tst_enum_data tst_opaque_data tst_string_data tst_vlen_data	\
	tst_comp tst_nans
TESTS += tst_create_files tst_group_data tst_enum_data tst_opaque_data	\
	tst_string_data tst_vlen_data tst_comp tst_nans \
	tst_netcdf4.sh tst_h_rdc0

check_PROGRAMS += tst_unicode
TESTS += tst_unicode

if EXTRA_TESTS
TESTS += tst_netcdf4_4.sh
endif
CLEANFILES += tst_solar_1.nc tst_solar_2.nc tst_solar_cmp.nc		\
	tst_group_data.nc tst_group_data.cdl tst_enum_data.nc		\
	tst_enum_data.cdl tst_opaque_data.nc tst_opaque_data.cdl	\
	tst_string_data.nc tst_string_data.cdl tst_vlen_data.nc		\
	tst_vlen_data.cdl tst_comp.nc tst_comp.cdl tst_unicode.nc	\
	tst_unicode.cdl tst_nans.nc tst_nans.cdl
tst_h_rdc0_CPPFLAGS = -I../nc_test ${AM_CPPFLAGS}

else # not USE_NETCDF4

# Find netcdf.h in libsrc.
AM_CPPFLAGS += -I../libsrc -I$(top_srcdir)/libsrc

# Link to netcdf-3 library.
if BUILD_DAP
LDADD += ../libnc-dap/libnc-dap.la
else
LDADD +=  ../libsrc/libnetcdf.la
endif

endif # USE_NETCDF4

# This is the program we're building, and it's sources.
bin_PROGRAMS = ncdump
ncdump_SOURCES = ncdump.c vardata.c dumplib.c indent.c	\
ncdump.h vardata.h dumplib.h indent.h \
isnan.h


# This is the man page.
man_MANS = ncdump.1

# These files all have to be included with the distribution.
EXTRA_DIST = run_tests.sh tst_64bit.sh tst_output.sh test0.cdl		\
ref_ctest1_nc4.cdl ref_ctest1_nc4c.cdl ref_tst_solar_1.cdl		\
ref_tst_solar_2.cdl tst_netcdf4.sh tst_netcdf4_4.sh ref_tst_small.cdl	\
tst_lengths.sh tst_ncml.cdl ref1.ncml ref_tst_group_data.cdl		\
ref_tst_enum_data.cdl ref_tst_opaque_data.cdl ref_tst_string_data.cdl	\
ref_tst_vlen_data.cdl ref_tst_comp.cdl ref_tst_unicode.cdl ref_tst_nans.cdl \
small.cdl small2.cdl $(man_MANS) run_utf8_tests.sh ref_tst_utf8.cdl

BUILT_SOURCES = ctest.c ctest64.c

ctest.c:
	$(top_builddir)/ncgen/ncgen -c -o ctest0.nc $(srcdir)/../ncgen/c0.cdl > $(srcdir)/ctest.c

ctest64.c:
	$(top_builddir)/ncgen/ncgen -v2 -c -o ctest0_64.nc $(srcdir)/../ncgen/c0.cdl > $(srcdir)/ctest64.c

MAINTAINERCLEANFILES = Makefile.in 


test: check
