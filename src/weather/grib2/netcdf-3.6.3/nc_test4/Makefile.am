# This is part of the netCDF package.
# Copyright 2005 University Corporation for Atmospheric Research/Unidata
# See COPYRIGHT file for conditions of use.
# 
# This entire directory will be skipped, unless the configure script
# is run with --enable-netcdf-4.
#
# $Id: Makefile.am,v 1.50 2008/04/15 16:48:44 ed Exp $

if USE_NETCDF4

# Set up flags to find libsrc4 version of libnetcdf.a and netcdf.h.
AM_CPPFLAGS = -I$(srcdir) -I$(top_srcdir)/libsrc4 
LDADD = ../libsrc4/libnetcdf.la -lhdf5_hl -lhdf5

AM_LDFLAGS =

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

# Our test programs and sources...
#check_PROGRAMS = tst_nc_test_file cdm_sea_soundings
check_PROGRAMS = cdm_sea_soundings
#tst_nc_test_file_SOURCES = tst_nc_test_file.c tests.h
cdm_sea_soundings_SOURCES = cdm_sea_soundings.c tests.h
TESTS = cdm_sea_soundings

if LARGE_FILE_TESTS
tst_large_SOURCES = tst_large.c tests.h
check_PROGRAMS += tst_large
TESTS += tst_large
endif # LARGE_FILE_TESTS

if BUILD_BENCHMARKS
bm_file_SOURCES = bm_file.c tests.h
tst_create_files_SOURCES = tst_create_files.c tests.h
check_PROGRAMS += tst_create_files bm_file
TESTS += tst_create_files run_bm_test1.sh run_bm_elena.sh run_bm_test2.sh 
if TEST_PARALLEL
TESTS += run_par_bm_test.sh
endif # TEST_PARALLEL
benchmarks: check
	./run_bm_radar_2D.sh	
	./run_bm_radar_2D_compression1.sh	
	./run_bm.sh	
endif # BUILD_BENCHMARKS

CLEANFILES = cdm_sea_soundings.nc tst_large.nc bm_chunking.nc		\
bm_radar.nc bm_radar1.nc radar_3d_compression_test.txt			\
radar_3d_compression.txt radar_2d_compression.txt			\
radar_3d_chunking.txt tst_floats_1D.nc tst_floats_1D.cdl		\
floats_1D_3.nc floats_1D.cdl tst_floats2_*.nc tst_ints2_*.nc		\
tst_shorts2_*.nc tst_elena_*.nc tst_simple*.nc tst_floats2_*.cdl	\
tst_ints2_*.cdl tst_shorts2_*.cdl tst_elena_*.cdl tst_simple*.cdl

# This are extra tests that will only be run if netcdf-4 is configured
# with --enable-parallel-tests.
if TEST_PARALLEL
check_PROGRAMS += tst_parallel tst_parallel3
CLEANFILES += tst_parallel.nc tst_parallel3.nc
TESTS += run_par_test.sh
endif

EXTRA_DIST = run_par_test.sh run_bm.sh run_bm_test1.sh run_bm_test2.sh	\
run_bm_radar_2D.sh run_bm_radar_2D_compression1.sh run_par_bm_test.sh	\
run_bm_elena.sh run_par_bm_radar_2D.sh run_bm_radar_2D_endianness1.sh

# If using dap, then force use of C++ for linking
# if BUILD_DAP
# nodist_EXTRA_cdm_sea_soundings_SOURCES=dummy.cc
# if LARGE_FILE_TESTS
# nodist_EXTRA_tst_large_SOURCES=dummy.cc
# endif
# if BUILD_BENCHMARKS
# nodist_EXTRA_tst_create_files_SOURCES=dummy.cc
# endif
# if TEST_PARALLEL
# nodist_EXTRA_tst_parallel_SOURCES=dummy.cc
# nodist_EXTRA_tst_parallel3_SOURCES=dummy.cc
# endif
# endif

endif # BUILD_NETCDF4


