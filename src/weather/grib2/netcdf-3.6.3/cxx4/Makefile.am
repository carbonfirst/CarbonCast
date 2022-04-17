## This is a automake file, part of Unidata's netCDF package.
# Copyright 2007, see the COPYRIGHT file for more information.

# This file builds the new C++-4 interface.

# $Id: Makefile.am,v 1.5 2007/08/13 16:05:17 ed Exp $

# Point pre-preprocessor to netcdf-4 directory (libsrc4).
AM_CPPFLAGS = -I$(top_srcdir)/libsrc4 
AM_LDFLAGS =

# Link to the netCDF-4 and the HDF5 libraries, and the C++ library.
LDADD = $(top_builddir)/cxx4/libnetcdf_c++4.la $(top_builddir)/libsrc4/libnetcdf.la -lhdf5_hl -lhdf5

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

# See comments in libsrc/Makefile.am about the version number.
libnetcdf_c__4_la_LDFLAGS = $(AM_LDFLAGS) -version-info 1:0:0 

# These headers will be installed in the users header directory.
include_HEADERS = netcdfcpp4.h 

# This is our output library. 
lib_LTLIBRARIES = libnetcdf_c++4.la

# Library source.
libnetcdf_c__4_la_SOURCES = ncatt.cpp ncdim.cpp ncexception.cpp	\
ncfile.cpp ncgroup.cpp ncvar.cpp ncvalues.cpp ncvalues.h

TESTFILES = tst_suiterunner$(EXEEXT) tst_file$(EXEEXT) tst_filerw$(EXEEXT) tst_simple$(EXEEXT)
tst_suiterunner_SOURCES = tst_suite.cpp tst_suiterunner.cpp tst_suite.h 
tst_file_SOURCES = tst_file.cpp
tst_filerw_SOURCES = tst_filerw.cpp
tst_simple_SOURCES = tst_simple.cpp

# Build and run these tests.
check_PROGRAMS = $(TESTFILES)
TESTS = $(TESTFILES)



