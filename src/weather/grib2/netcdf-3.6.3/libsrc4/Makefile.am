## This is a automake file, part of Unidata's netCDF package.
# Copyright 2005, see the COPYRIGHT file for more information.

# This automake file generates the Makefile to build netCDF-4. The
# generated makefile is not run unless the user selected to build
# netCDF-4.

# $Id: Makefile.am,v 1.87 2008/06/09 16:32:46 ed Exp $

netcdf.h:
	cp netcdf_base.h netcdf.h

# Cause C preprocessor to search current and parent directory.
AM_CPPFLAGS = -I$(top_srcdir)/libsrc

# Linker needs to search current directory when building tests.
AM_LDFLAGS = 

# If the user specified a root location for HDF5, use it.
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

# Tell automake that netcdf.h is a header file we want to install.
include_HEADERS = netcdf.h

# Construct the netcdf.h file.
# BUILT_SOURCES = netcdf.h
# netcdf.h:
# if BUILD_PARALLEL
# 	sed '/#include <errno.h>/a\/* mpi.h included by configure. *\/\n#include <mpi.h>' netcdf_base.h > netcdf.h
# else
# 	sed '/#include <errno.h>/a\/* These defs added by netCDF configure because parallel HDF5 is not present. *\/\n#define MPI_Comm int\n#define MPI_Info int\n#define MPI_COMM_WORLD\n#define MPI_INFO_NULL' netcdf_base.h > netcdf.h
# endif

# This is our output. The big enchilada.
lib_LTLIBRARIES = libnetcdf.la

# Our output library will also include contents of the netcdf3
# convenience library and optionally the libnc-dap library
if BUILD_DAP
libnetcdf_la_LIBADD = ../libnc-dap/libnc-dap.la
else
libnetcdf_la_LIBADD = ../libsrc/libnetcdf3.la
endif

# Include netcdf-2 unless v2 has been turned off..
if BUILD_V2
libnetcdf_la_LIBADD += ../libsrc/libnetcdf2.la
TST_V2 = tst_v2 
endif

# Netcdf-4 source.
libnetcdf_la_SOURCES = nc4attr.c nc4internal.c nc4var.c netcdf3.h	\
nc4dim.c nc4internal.h ncfunc.c nc4file.c netcdf.h error.c error.h	\
nc4internal.h netcdf3.h nc4grp.c nc4type.c nc4hdf.c		

# If we are not building separate fortran libraries, then include
# their functions in the C library.
if !BUILD_SEPARATE_FORTRAN

# If F77 is built, include it's convenience library. If F90 is built,
# it will also be part of this convenience library.
if BUILD_F77
libnetcdf_la_LIBADD += ../fortran/libnetcdff.la
endif

endif # !BUILD_SEPARATE_FORTRAN
# These linker flags specify libtool version info.
libnetcdf_la_LDFLAGS = -version-number 5:0:0

# These programs are all built for make check in this directory.
my_tests = tst_h_files tst_h_atts tst_h_atts2 tst_h_vars tst_h_vars2	\
tst_h_grps tst_h_compounds tst_h_compounds2 tst_h_wrt_cmp tst_h_rd_cmp	\
tst_h_vl tst_h_opaques tst_h_strings tst_h_dimscales tst_h_dimscales2	\
tst_h_enums tst_lists tst_dims tst_files tst_vars tst_varms		\
tst_unlim_vars tst_atts tst_converts tst_converts2 tst_grps		\
tst_compounds tst_compounds2 tst_vl tst_h_vl2 tst_opaques tst_strings	\
tst_interops tst_enums tst_vars2 tst_utf8 $(TST_V2)
check_PROGRAMS = $(my_tests)

if TEST_PARALLEL
check_PROGRAMS += tst_h_par
endif

EXTRA_DIST = ref_tst_compounds.nc ref_tst_h_compounds.h5 netcdf_base.h	\
run_par_tests.sh

# (The above does not include tst_h_converts, which won't work until I
# sort out the MAX_INT problem. - Ed)

# These linker flags will be applied to all test program compiles.
LDADD = ${lib_LTLIBRARIES} -lhdf5_hl -lhdf5

# This header is used by all test programs.
noinst_HEADERS = nc_tests.h

# This will run all the test programs.
TESTS = $(my_tests)
if TEST_PARALLEL
TESTS += run_par_tests.sh
endif

# Clean up. Each test program creates one data file, with the same
# name as the test program, and either a .h5 or .nc, for "pure" HDF5
# files and netCDF-4 files.
MAINTAINERCLEANFILES = Makefile.in
CLEANFILES = tst_nc_converts.nc tst_h_files.h5 tst_h_converts.h5	\
tst_h_atts.h5 tst_h_atts2.h5 tst_h_vars.h5 tst_h_vars2.h5		\
tst_h_grps.h5 tst_h_compounds.h5 tst_h_compounds2.h5 tst_h_wrt_cmp.h5	\
tst_h_vl.h5 tst_h_opaques.h5 tst_h_strings.h5 tst_h_converts.h5		\
tst_h_dimscales.h5 tst_h_dimscales2.h5 tst_h_enums.h5 tst_lists.nc	\
tst_dims.nc tst_v2.nc tst_files.nc tst_vars.nc tst_varms.nc		\
tst_unlim_vars.nc tst_atts.nc tst_converts.nc tst_converts2.nc		\
tst_grps.nc tst_compounds.nc tst_compounds2.nc tst_vl.nc		\
tst_opaques.nc tst_strings.nc tst_interops.h5 tst_enums.nc		\
tst_coords.nc tst_vars2.nc tst_pres_temp_4D_classic.nc			\
tst_pres_temp_4D_64bit_offset.nc tst_pres_temp_4D_netcdf4.nc		\
tst_pres_temp_4D_netcdf4_classic.nc tst_h_par.nc tst_utf8.nc
DISTCLEANFILES = netcdf.h

test: check

# if BUILD_DAP
# # Force use of c++ in linking
# nodist_EXTRA_tst_h_files_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_atts_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_atts2_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_vars_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_vars2_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_grps_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_compounds_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_compounds2_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_wrt_cmp_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_rd_cmp_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_vl_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_opaques_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_strings_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_dimscales_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_dimscales2_SOURCES=dummy.cc
# nodist_EXTRA_tst_h_enums_SOURCES=dummy.cc
# nodist_EXTRA_tst_lists_SOURCES=dummy.cc
# nodist_EXTRA_tst_dims_SOURCES=dummy.cc
# nodist_EXTRA_tst_files_SOURCES=dummy.cc
# nodist_EXTRA_tst_vars_SOURCES=dummy.cc
# nodist_EXTRA_tst_varms_SOURCES=dummy.cc
# nodist_EXTRA_tst_unlim_vars_SOURCES=dummy.cc
# nodist_EXTRA_tst_atts_SOURCES=dummy.cc
# nodist_EXTRA_tst_converts_SOURCES=dummy.cc
# nodist_EXTRA_tst_converts2_SOURCES=dummy.cc
# nodist_EXTRA_tst_grps_SOURCES=dummy.cc
# nodist_EXTRA_tst_compounds_SOURCES=dummy.cc
# nodist_EXTRA_tst_compounds2_SOURCES=dummy.cc
# nodist_EXTRA_tst_vl_SOURCES=dummy.cc
# nodist_EXTRA_tst_opaques_SOURCES=dummy.cc
# nodist_EXTRA_tst_strings_SOURCES=dummy.cc
# nodist_EXTRA_tst_interops_SOURCES=dummy.cc
# nodist_EXTRA_tst_enums_SOURCES=dummy.cc
# nodist_EXTRA_tst_vars2_SOURCES=dummy.cc
# nodist_EXTRA_tst_v2_SOURCES=dummy.cc
# endif
