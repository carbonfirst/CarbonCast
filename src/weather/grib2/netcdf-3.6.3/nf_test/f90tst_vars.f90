!     This is part of the netCDF package.
!     Copyright 2006 University Corporation for Atmospheric Research/Unidata.
!     See COPYRIGHT file for conditions of use.

!     This program tests netCDF-4 variable functions from fortran.

!     $Id: f90tst_vars.f90,v 1.6 2008/04/30 17:10:11 ed Exp $

program f90tst_vars
  use typeSizes
  use netcdf
  implicit none
  
  ! This is the name of the data file we will create.
  character (len = *), parameter :: FILE_NAME = "f90tst_vars.nc"

  ! We are writing 2D data, a 6 x 12 grid. 
  integer, parameter :: MAX_DIMS = 2
  integer, parameter :: NX = 6, NY = 12
  integer :: ncid, varid, dimids(MAX_DIMS), chunksizes(MAX_DIMS), chunksizes_in(MAX_DIMS)
  integer :: x_dimid, y_dimid, contig
  integer :: data_out(NY, NX), data_in(NY, NX)
  integer :: mode_flag
  integer :: nvars, ngatts, ndims, unlimdimid, file_format
  integer :: x, y, retval

  print *,'*** Testing definition of netCDF-4 vars from Fortran 90.'

  ! Create some pretend data.
  do x = 1, NX
     do y = 1, NY
        data_out(y, x) = (x - 1) * NY + (y - 1)
     end do
  end do

  ! Create the netCDF file. 
  mode_flag = IOR(nf90_netcdf4, nf90_classic_model) 
  retval = nf90_create(FILE_NAME, mode_flag, ncid)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! Define the dimensions.
  retval = nf90_def_dim(ncid, "x", NX, x_dimid)
  if (retval /= nf90_noerr) call handle_err(retval)
  retval = nf90_def_dim(ncid, "y", NY, y_dimid)
  if (retval /= nf90_noerr) call handle_err(retval)
  dimids =  (/ y_dimid, x_dimid /)

  ! Define the variable. 
  retval = nf90_def_var(ncid, "data", NF90_INT, dimids, varid)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! Set up chunking.
  chunksizes = (/ NY, NX /)
  retval = nf90_def_var_chunking(ncid, varid, 0, chunksizes)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! With classic model netCDF-4 file, enddef must be called.
  retval = nf90_enddef(ncid)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! Write the pretend data to the file.
  retval = nf90_put_var(ncid, varid, data_out)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! Close the file. 
  retval = nf90_close(ncid)
  if (retval /= nf90_noerr) call handle_err(retval)

  ! Reopen the file.
  retval = nf90_open(FILE_NAME, nf90_nowrite, ncid)
  if (retval /= nf90_noerr) call handle_err(retval)
  
  ! Check some stuff out.
  retval = nf90_inquire(ncid, ndims, nvars, ngatts, unlimdimid, file_format)
  if (retval /= nf90_noerr) call handle_err(retval)
  if (ndims /= 2 .or. nvars /= 1 .or. ngatts /= 0 .or. unlimdimid /= -1 .or. &
       file_format /= nf90_format_netcdf4_classic) stop 2

  retval = nf90_inq_var_chunking(ncid, varid, contig, chunksizes_in)
  if (retval /= nf90_noerr) call handle_err(retval)
  if (chunksizes_in(1) /= chunksizes(1) .or. chunksizes_in(2) /= chunksizes(2)) &
       stop 2

  ! Close the file. 
  retval = nf90_close(ncid)
  if (retval /= nf90_noerr) call handle_err(retval)

  print *,'*** SUCCESS!'

contains
!     This subroutine handles errors by printing an error message and
!     exiting with a non-zero status.
  subroutine handle_err(errcode)
    use netcdf
    implicit none
    integer, intent(in) :: errcode
    
    if(errcode /= nf90_noerr) then
       print *, 'Error: ', trim(nf90_strerror(errcode))
       stop 2
    endif
  end subroutine handle_err
end program f90tst_vars

