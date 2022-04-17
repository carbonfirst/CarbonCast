## This is a automake file, part of Unidata's netCDF package.
# Copyright 2005, see the COPYRIGHT file for more information.
# This file builds and runs the ncgen program.

# $Id: Makefile.am,v 1.30 2008/04/21 19:55:09 dmh Exp $

# Build ncgen from the listed sources.
bin_PROGRAMS = ncgen
ncgen_SOURCES = main.c load.c ncgentab.c escapes.c getfill.c init.c	\
genlib.c generic.h ncgen.h genlib.h ncgentab.h

man_MANS = ncgen.1

# These files all need to be distributed.
EXTRA_DIST = ncgenyy.c ncgen.l c0.cdl run_tests.sh run_nc4_tests.sh	\
$(man_MANS)

# This shell script causes ncgen to build a classic and a 64-bit
# offset file from a cdl file shipped with the distribution.
TESTS = run_tests.sh 

# The tests produce these files.
CLEANFILES = c0.nc c0_64.nc

if USE_NETCDF4

# This shell script causes ncgen to build a netcdf-4 and netcdf-4
# classic file from a cdl file shipped with the distribution.
TESTS += run_nc4_tests.sh

# The nc4 tests produce these files.
CLEANFILES += c0_4.nc c0_4c.nc

AM_LDFLAGS =
AM_CPPFLAGS =

# If netcdf4 is built, point at it's directory. 
AM_CPPFLAGS += -I.. -I../libsrc4 -I$(top_srcdir)/libsrc4

# Link to netcdf-4 library, and the HDF5 libraries.
LDADD = ../libsrc4/libnetcdf.la -lhdf5_hl -lhdf5

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

else # not USE_NETCDF4

# Look for netcdf.h in libsrc.
AM_CPPFLAGS = -I.. -I../libsrc -I$(top_srcdir)/libsrc

# Link to the netcdf-3 library.
if BUILD_DAP
LDADD = ../libnc-dap/libnc-dap.la
else
LDADD = ../libsrc/libnetcdf.la
endif

endif # USE_NETCDF4

# Here is the sequence of tests that need to be run:
# ./ncgen -b -o c0.nc c0.cdl
# ../ncdump/ncdump -n c1 c0.nc > c1.cdl
# *** ncgen -b test successful ***
# ./ncgen -c -o ctest0.nc c0.cdl > ctest.c && \
# cc -o ctest -g  -I../libsrc -I.   -Df2cFortran ctest.c ../libsrc/libnetcdf.a  && \
# ./ctest	&& \
# ../ncdump/ncdump -n c1 ctest0.nc > ctest1.cdl
# *** ncgen -c test successful ***

MAINTAINERCLEANFILES = Makefile.in

test: check

# This is used if someone wants to rebuild ncgenyy.c
# Otherwise never invoked, but records how to do it. 
ncgenyy.c:
	flex -8 ncgen.l
	mv lex.yy.c ncgenyy.c

# if BUILD_DAP
# # Force use of c++ in linking
# nodist_EXTRA_ncgen_SOURCES=dummy.cc
# endif
