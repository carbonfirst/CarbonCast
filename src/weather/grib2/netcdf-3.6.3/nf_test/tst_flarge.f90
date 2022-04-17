! Copyright 2007, UCAR/Unidata. See netcdf/COPYRIGHT file for copying
! and redistribution conditions.

! This program tests large files (> 4 GB) in netCDF-4. 

! $Id: tst_flarge.f90,v 1.1 2007/08/19 11:35:32 ed Exp $
program tst_flarge
  use typeSizes
  use netcdf
  implicit none

  integer :: ncFileID, dimID, varID1, varID2 
  integer, parameter :: MAX_CLASSIC_BYTES = 2147483644
  integer, parameter :: MAX_64OFFSET_BYTES = 4294967292
  character (len = *), parameter :: fileName = "tst_flarge.nc"
  character (len = *), parameter :: dimName = "really_big_dimension"
  character (len = *), parameter :: var1Name = "TweedleDum"
  character (len = *), parameter :: var2Name = "TweedleDee"
  integer :: counter                      
  real, dimension(MAX_CLASSIC_BYTES) :: var1
  real, dimension(MAX_CLASSIC_BYTES) :: var2

  print *,'*** Testing netCDF-4 large files from Fortran 90 API.'

  ! Create the file with 2 NF_DOUBLE vars, each with one really long dimension.
  call check(nf90_create(path = trim(fileName), cmode = nf90_hdf5, ncid = ncFileID))
  call check(nf90_def_dim(ncid = ncFileID, name = dimName, len = MAX_CLASSIC_BYTES, dimid = dimID))
  call check(nf90_def_var(ncid = ncFileID, name = var1Name, xtype = nf90_double,     &
       dimids = (/ dimID /), varID = varID1) )
  call check(nf90_def_var(ncid = ncFileID, name = var2Name, xtype = nf90_double,     &
       dimids = (/ dimID /), varID = varID2) )

!   ! Write the pressure variable. Write a slab at a time to check incrementing.
!   pressure = 949. + real(reshape( (/ (counter, counter = 1, numLats * numLons * numFrTimes) /),  &
!        (/ numLons, numLats, numFrTimes /) ) )
!   call check(nf90_put_var(ncFileID, pressVarID, pressure(:, :, 1:1)) )
!   call check(nf90_put_var(ncFileID, pressVarID, pressure(:, :, 2:2), start = (/ 1, 1, 2 /)) )

  call check(nf90_close(ncFileID))

  ! Now open the file to read and check a few values
  call check(nf90_open(trim(fileName), NF90_NOWRITE, ncFileID))
!   call check(nf90_inq_varid(ncFileID,"frtime",frTimeVarID))
!   call check(nf90_get_att(ncFileID,frTimeVarID,"units",frTimeUnits))
!   if(frTimeUnits .ne. "hours") then
!      print *, 'Attribute value not what was written:', frTimeUnits
!      stop 2
!   endif
  call check(nf90_close(ncFileID))

  print *,'*** SUCCESS!'

contains
  ! Internal subroutine - checks error status after each netcdf, prints out text message each time
  !   an error code is returned. 
  subroutine check(status)
    integer, intent ( in) :: status

    if(status /= nf90_noerr) then 
       print *, trim(nf90_strerror(status))
       stop 2
    end if
  end subroutine check
end program tst_flarge
