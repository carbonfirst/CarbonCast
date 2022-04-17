C     This is part of the netCDF package.
C     Copyright 2005 University Corporation for Atmospheric Research/Unidata.
C     See COPYRIGHT file for conditions of use.

C     This is the error handling function for some of the F77
C     tests. This error handler comes from the netcdf tutorial.

C     $Id: handle_err.f,v 1.2 2008/02/28 16:09:51 ed Exp $

C     This subroutine handles errors by printing an error message and
C     exiting with a non-zero status.
      subroutine handle_err(errcode)
      implicit none
      include '../fortran/netcdf.inc'
      integer errcode

      print *, 'Error: ', nf_strerror(errcode)
      stop 2
      end

