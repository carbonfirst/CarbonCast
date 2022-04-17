## This is a automake file, part of Unidata's netCDF package.
# Copyright 2005-2006, see the COPYRIGHT file for more information.

# This file builds and runs the following: 

# The nf_test program, which tests the netCDF fortran 77 interface.

# The ftest program, which tests the netCDF fortran 77 V2
# interface. (Unless V2 is disabled).

# Test programs ftst_vars, ftst_vars2, ftst_vars3, ftst_vars4,
# ftst_vars5, ftst_types, ftst_types2, and ftst_groups, if netCDF-4 is
# enabled.

# The tst_f90 and f90tst_vars programs, which tests the netCDF fortran
# 90 interface. (Unless F90 API is disabled).

# $Id: Makefile.am,v 1.60 2008/04/21 14:31:54 ed Exp $

LDADD =
AM_LDFLAGS = 

# nf_test is the main test program. tst_f77_v2 is a small extra test
# program.
TESTPROGRAMS = nf_test
nf_test_SOURCES = test_get.m4 test_put.m4 nf_error.F nf_test.F	\
test_read.F test_write.F util.F fortlib.c tests.inc

# Cleaning up files created during the process.
CLEANFILES = scratch.nc test.nc copy.nc fills.nc tst_f77_v2.nc
MAINTAINERCLEANFILES = Makefile.in test_get.F test_put.F

# Did the user build the V2 F77 API? If so, run this test.
if BUILD_V2
TESTPROGRAMS += tst_f77_v2
tst_f77_v2_SOURCES = tst_f77_v2.F
CLEANFILES += tst_f77_v2.nc
endif # BUILD_V2

# If building a separate fortran library, include it so the tests can
# find it.
if BUILD_SEPARATE_FORTRAN
LDADD += ../fortran/libnetcdff.la -lm
# Point pre-processor and linker to directory with C lib.
AM_CPPFLAGS = -I$(NETCDF_C_LIB)/include
AM_LDFLAGS += -L$(NETCDF_C_LIB)/lib
endif

# Some fortran compilers think your files should not have an .f90
# extension! The value of FCFLAGS_f90 is set in the configure script,
# based on the fortran compiler.
AM_FCFLAGS = $(FCFLAGS_f90) -I$(top_srcdir)/fortran -I$(top_builddir)/f90
AM_FFLAGS = -I$(top_srcdir)/fortran

# Is the user building netCDF-4?
if USE_NETCDF4

# Add these netCDF-4 f77 test programs.
TESTPROGRAMS += ftst_vars ftst_vars2 ftst_vars3 ftst_vars4 ftst_vars5	\
ftst_types ftst_types2 ftst_groups
ftst_types_SOURCES = ftst_types.F fortlib.c handle_err.f
ftst_types2_SOURCES = ftst_types2.F fortlib.c handle_err.f
ftst_vars_SOURCES = ftst_vars.F fortlib.c handle_err.f
ftst_vars2_SOURCES = ftst_vars2.F fortlib.c handle_err.f
ftst_vars3_SOURCES = ftst_vars3.F fortlib.c handle_err.f
ftst_vars4_SOURCES = ftst_vars4.F fortlib.c handle_err.f
ftst_vars5_SOURCES = ftst_vars5.F fortlib.c handle_err.f
ftst_groups_SOURCES = ftst_groups.F fortlib.c handle_err.f
CLEANFILES += ftst_vars.nc ftst_vars2.nc ftst_vars3.nc ftst_vars4.nc	\
ftst_vars5.nc ftst_types.nc ftst_types2.nc ftst_groups.nc

# Add these netCDF-4 f90 test programs.
if BUILD_F90
TESTPROGRAMS += f90tst_vars tst_types
f90tst_vars_SOURCES = f90tst_vars.f90
tst_types_SOURCES = tst_types.f90
CLEANFILES += f90tst_vars.nc tst_types.nc

# This is the netCDF-4 F90 large file test.
if LARGE_FILE_TESTS
TESTPROGRAMS += tst_flarge
tst_flarge_SOURCES = tst_flarge.f90
CLEANFILES += tst_flarge.nc
endif # LARGE_FILE_TESTS

# This is an f90 benchmark.
if BUILD_BENCHMARKS
TESTPROGRAMS += tst_io
tst_io_SOURCES = tst_io.f90
CLEANFILES += tst_io1.nc tst_io2.nc tst_io3.nc tst_io4.nc tst_io5.nc	\
tst_io6.nc tst_io7.nc tst_io8.nc tst_io9.nc tst_io10.nc tst_io11.nc
endif #BUILD_BENCHMARKS

endif #BUILD_F90

# If the user specified a root for HDF5, use it.
if USE_HDF5_DIR
AM_FFLAGS += -I@HDF5DIR@/include
AM_FCFLAGS += -I@HDF5DIR@/include
AM_LDFLAGS += -L@HDF5DIR@/lib
endif

# If the user specified a root location for ZLIB, use it.
if USE_ZLIB_DIR
AM_FFLAGS += -I@ZLIBDIR@/include
AM_FCFLAGS += -I@ZLIBDIR@/include
AM_LDFLAGS += -L@ZLIBDIR@/lib
endif

# If the user specified a root location for SZLIB, use it.
if USE_SZLIB_DIR
AM_FFLAGS += -I@SZLIBDIR@/include
AM_FCFLAGS += -I@SZLIBDIR@/include
AM_LDFLAGS += -L@SZLIBDIR@/lib
endif

if BUILD_C

# Find header file in libsrc4 directory.
AM_FFLAGS += -I$(top_srcdir)/libsrc4
AM_FCFLAGS += -I$(top_srcdir)/libsrc4

# Include the C library in the link.
LDADD += ../libsrc4/libnetcdf.la 

else

AM_FFLAGS += -I@NETCDF_C_LIB@/include
AM_FCFLAGS += -I@NETCDF_C_LIB@/include
AM_LDFLAGS += -L@NETCDF_C_LIB@/lib
LDADD += -lnetcdf

endif # BUILD_C

# Since netCDF-4 is being built link to HDF5 and HDF5 high-level
# libraries.
LDADD += -lhdf5_hl -lhdf5

else # not USE_NETCDF4

if BUILD_C

# Find header file in libsrc directory.
AM_FFLAGS += -I$(top_srcdir)/libsrc -I$(top_srcdir)/fortran
AM_FCFLAGS += -I$(top_srcdir)/libsrc -I$(top_srcdir)/fortran 

# Include the C library in the link.
if BUILD_DAP
LDADD += ../libnc-dap/libnc-dap.la
else
LDADD += ../libsrc/libnetcdf.la
endif

else # not BUILD_C

AM_FFLAGS += -I@NETCDF_C_LIB@/include
AM_FCFLAGS += -I@NETCDF_C_LIB@/include
AM_LDFLAGS += -L@NETCDF_C_LIB@/lib
LDADD += -lnetcdf

endif # BUILD_C

endif # USE_NETCDF4

if BUILD_C
# This is the fortran v2 test. It depends on the utilities being built
# to generate it's input file.
if BUILD_V2
if BUILD_UTILITIES
TESTPROGRAMS += ftest
ftest_SOURCES = ftest.F fortlib.c 
CLEANFILES += test.nc
endif # BUILD_UTILITIES
endif # BUILD_V2
endif #BUILD_C

# This is the netCDF-3 F90 test.
if BUILD_F90
AM_FFLAGS += @MOD_FLAG@../f90
AM_FCFLAGS += @MOD_FLAG@../f90
TESTPROGRAMS += tst_f90
tst_f90_SOURCES = tst_f90.f90
CLEANFILES += tst_f90.nc
endif

check_PROGRAMS = $(TESTPROGRAMS)

if BUILD_UTILITIES
# The create_fills shell creates the file fills.nc, needed by later
# tests.
TESTS = create_fills.sh $(TESTPROGRAMS)
else
TESTS = $(TESTPROGRAMS)
endif

# Tell make how to turn .m4 files into .F files.
.m4.F:
	m4 $(M4FLAGS) $< >$@

# test_get.F and test_put.f need to be distributed, so that the user
# need not have m4. fills.nc is used by test program ftest.
EXTRA_DIST = test_get.F test_put.F fills.cdl create_fills.sh

test: check

# There is a linking conflict here. Do we link with C++ and add
# the necessary fortran library or do we link with fortran and
# add the necessary C++ library.  The latter is likely to be
# more standard so we do that.
if BUILD_DAP
# Do not use the nodist_ dummy mechanism
LDADD += -lstdc++
endif
