/*
This file is part of netcdf-4, a netCDF-like interface for HDF5, or a
HDF5 backend for netCDF, depending on your point of view.

This file handles the nc4 attribute functions.

Copyright 2003-2006, University Corporation for Atmospheric
Research. See COPYRIGHT file for copying and redistribution
conditions.

$Id: nc4file.c,v 1.57 2008/06/09 16:33:05 ed Exp $
*/

#include "netcdf.h"
#include "nc4internal.h"

extern NC_FILE_INFO_T *nc_file;

/* This is set by nc_set_default_format in libsrc/nc.c. */
extern int default_create_format;

/* To turn off HDF5 error messages, I have to catch an early
   invocation of a netcdf function. */
static int virgin = 1;

/* These are used to assign an ncid when a file is opened or
   created. We need both the number of open files and the last ncid
   used, which may be > the number of open files, because some files
   have been closed. */
static int numfiles = 0;
static short last_file_id = 0;

/* This will return the length of a netcdf data type in bytes. Since
   we haven't added any new types, I just call the v3 function.
   Ed Hartnett 10/43/03
*/
int
nc4typelen(nc_type type)
{
   switch(type){
      case NC_BYTE:
      case NC_CHAR:
      case NC_UBYTE:
	 return 1;
      case NC_USHORT:
      case NC_SHORT:
	 return 2;
      case NC_FLOAT:
      case NC_INT:
      case NC_UINT:
	 return 4;
      case NC_DOUBLE: 
      case NC_INT64:
      case NC_UINT64:
	 return 8;
   }
   return -1;
}

/* Given a filename, check to see if it is a HDF5 file. */
#define MAGIC_NUMBER_LEN 4
static int
nc_check_for_hdf5(const char *path, int use_parallel, MPI_Comm comm, MPI_Info info, 
		  int *hdf_file)
{
   char blob[MAGIC_NUMBER_LEN];
   
   assert(hdf_file && path);
   LOG((3, "nc_check_for_hdf5: path %s", path));

/* Get the 4-byte blob from the beginning of the file. Don't use posix
 * for parallel, use the MPI functions instead. */
#ifdef USE_PARALLEL
   if (use_parallel)
   {
      MPI_File fh;
      int retval;

      if ((retval = MPI_File_open(comm, (char *)path, MPI_MODE_RDONLY,
				  info, &fh)) != MPI_SUCCESS)
	 return NC_EPARINIT;
      if ((retval = MPI_File_read(fh, blob, MAGIC_NUMBER_LEN, MPI_CHAR,
				  MPI_STATUS_IGNORE)) != MPI_SUCCESS)
	 return NC_EPARINIT;
      if ((retval = MPI_File_close(&fh)) != MPI_SUCCESS)
	 return NC_EPARINIT;
   }
   else
#endif /* USE_PARALLEL */
   {
      FILE *fp;
      if (!(fp = fopen(path, "r")) ||
	  fread(blob, MAGIC_NUMBER_LEN, 1, fp) != 1)
	 return errno;
      fclose(fp);
   }

   /* Ignore the first byte. */
   if (blob[1] == 'H' && blob[2] == 'D' && blob[3] == 'F')
      (*hdf_file)++;
   else
      *hdf_file = 0;

   return NC_NOERR;
}
   
/* Create a HDF5/netcdf-4 file. In this case, ncid has already been
 * selected in ncfunc.c. */
static int
nc4_create_file(const char *path, int cmode, MPI_Comm comm,
		MPI_Info info, NC_FILE_INFO_T *nc) 
{
   hid_t fcpl_id = H5P_DEFAULT, fapl_id = H5P_DEFAULT;
   unsigned flags = (cmode & NC_NOCLOBBER) ? 
      H5F_ACC_EXCL : H5F_ACC_TRUNC;
   FILE *fp;
   int retval = NC_NOERR;

   LOG((3, "nc4_create_file: path %s mode 0x%x", path, cmode));
   assert(nc && path);

   /* If this file already exists, and NC_NOCLOBBER is specified,
      return an error. */
   if ((cmode & NC_NOCLOBBER) && (fp = fopen(path, "r")))
   {
      fclose(fp);
      return NC_EEXIST;
   }
   
   /* Add necessary structs to hold netcdf-4 file data. */
   if ((retval = nc4_nc4f_list_add(nc, path, (NC_WRITE | cmode))))
      BAIL(retval);
   assert(nc->nc4_info && nc->nc4_info->root_grp);

   /* Need this access plist to control how HDF5 handles open onjects
    * on file close. (Setting H5F_CLOSE_SEMI will cause H5Fclose to
    * fail if there are any open objects in the file. */
   if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0)
      BAIL(NC_EHDFERR);
/*   if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_SEMI))*/
   if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_STRONG))
      BAIL(NC_EHDFERR);

#ifdef USE_PARALLEL
   /* If this is a parallel file create, set up the file creation
      property list. */
   if ((cmode & NC_MPIIO) || (cmode & NC_MPIPOSIX))
   {
      nc->nc4_info->parallel++;
      if (cmode & NC_MPIIO)  /* MPI/IO */
      {
	 LOG((4, "creating parallel file with MPI/IO"));
	 if (H5Pset_fapl_mpio(fapl_id, comm, info) < 0)
	    BAIL(NC_EPARINIT);
      }
      else /* MPI/POSIX */
      {
	 LOG((4, "creating parallel file with MPI/posix"));
	 if (H5Pset_fapl_mpiposix(fapl_id, comm, 0) < 0)
	    BAIL(NC_EPARINIT);
      }
   }
#endif /* USE_PARALLEL */
   
   /* Set latest_format in access propertly list and
    * H5P_CRT_ORDER_TRACKED in the creation property list. This turns
    * on HDF5 creation ordering. */
   if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0)
      BAIL(NC_EHDFERR);
   if ((fcpl_id = H5Pcreate(H5P_FILE_CREATE)) < 0)
      BAIL(NC_EHDFERR);
   if (H5Pset_link_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED |
					    H5P_CRT_ORDER_INDEXED)) < 0)
      BAIL(NC_EHDFERR);
   if (H5Pset_attr_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED |
					    H5P_CRT_ORDER_INDEXED)) < 0)
      BAIL(NC_EHDFERR);

   /* Create the file. */
   if ((nc->nc4_info->hdfid = H5Fcreate(path, flags, fcpl_id, fapl_id)) < 0) 
      BAIL(NC_EFILEMETA);

   /* Open the root group. */
   if ((nc->nc4_info->root_grp->hdf_grpid = H5Gopen2(nc->nc4_info->hdfid, "/", 
						     H5P_DEFAULT)) < 0)
      BAIL(NC_EFILEMETA);

   /* Release the property list. */
   if (H5Pclose(fapl_id) < 0)
      BAIL(NC_EPARINIT);

   /* Define mode gets turned on automatically on create. */
   nc->nc4_info->flags |= NC_INDEF;

   return NC_NOERR;

 exit:
   if (nc->nc4_info->hdfid > 0) H5Fclose(nc->nc4_info->hdfid);
   return retval;
}

static int
nc_create_file(const char *path, int cmode, size_t initialsz, 
	       int basepe, size_t *chunksizehintp, MPI_Comm comm, 
	       MPI_Info info, int *ncidp)
{
   int res;

   assert(ncidp); assert(path);
   LOG((1, "nc_create_file: path %s cmode 0x%x comm %d info %d",
	path, cmode, comm, info));
   
   /* If this is our first file, turn off HDF5 error messages. */
   if (virgin)
   {
      if (H5Eset_auto(NULL, NULL) < 0)
	 LOG((0, "Couldn't turn off HDF5 error messages!"));
      LOG((1, "HDF5 error messages have been turned off."));
      virgin = 0;
   }

   /* Check the cmode for validity. */
   if (cmode & ~(NC_NOCLOBBER | NC_64BIT_OFFSET | NC_NETCDF4 | NC_CLASSIC_MODEL | 
		 NC_SHARE | NC_MPIIO | NC_MPIPOSIX | NC_LOCK) ||
       (cmode & NC_MPIIO && cmode & NC_MPIPOSIX) ||
       (cmode & NC_64BIT_OFFSET && cmode & NC_NETCDF4))
      return NC_EINVAL;

   /* Allocate the storage for this file info struct, and fill it with
      zeros. This add the file metadata to the front of the global
      nc_file list. */
   if ((res = nc4_file_list_add((++last_file_id << ID_SHIFT))))
      return res;

   /* Apply default create format. */
   if (default_create_format == NC_FORMAT_64BIT)
      cmode |= NC_64BIT_OFFSET;
   else if (default_create_format == NC_FORMAT_NETCDF4)
      cmode |= NC_NETCDF4;
   else if (default_create_format == NC_FORMAT_NETCDF4_CLASSIC)
   {
      cmode |= NC_NETCDF4;
      cmode |= NC_CLASSIC_MODEL;
   }
   LOG((2, "cmode after applying default format: 0x%x", cmode));

   /* Check to see if we want a netcdf3 or netcdf4 file. Open it, and
      call the appropriate nc*_create. */
   if (cmode & NC_NETCDF4) 
   {
      nc_file->int_ncid = nc_file->ext_ncid;
      res = nc4_create_file(path, cmode, comm, info, nc_file);
   } 
   else 
   {
      res = nc3__create_mp(path, cmode, initialsz, basepe, 
			   chunksizehintp, &(nc_file->int_ncid));
   }
   
   /* If nc*_create worked, increment our numbers, otherwise, free the
      memory we allocated for this file. */
   if (!res)
   {
      *ncidp = nc_file->ext_ncid;
      numfiles++;
   } 
   else 
   {
      last_file_id--;
      nc4_file_list_del(nc_file);
   }

   return res;
}

int
nc_create(const char *path, int cmode, int *ncidp)
{
   return nc_create_file(path, cmode, 0, 0, NULL, 0, 0, ncidp);
}

int
nc__create(const char *path, int cmode, size_t initialsz,
	   size_t *chunksizehintp, int *ncidp)
{
   return nc_create_file(path, cmode, initialsz, 0, 
			 chunksizehintp, 0, 0, ncidp);
}

int
nc__create_mp(const char *path, int cmode, size_t initialsz, int basepe,
	      size_t *chunksizehintp, int *ncidp)
{
   return nc_create_file(path, cmode, initialsz, basepe, 
			 chunksizehintp, 0, 0, ncidp);
}

/*#ifdef USE_PARALLEL*/
int
nc_create_par(const char *path, int cmode, MPI_Comm comm, 
	      MPI_Info info, int *ncidp)
{
   /* Only netcdf-4 files can be parallel. */
   if (!cmode & NC_NETCDF4)
      return NC_ENOTNC4;

   /* Must use either MPIIO or MPIPOSIX. Default to the former. */
   if (!(cmode & NC_MPIIO || cmode & NC_MPIPOSIX))
      cmode |= NC_MPIIO;
      
   return nc_create_file(path, cmode, 0, 0, NULL, comm, info, ncidp);
}
/*#endif*/ /* USE_PARALLEL */

/* Open a netcdf-4 file. Things have already been kicked off in
 * ncfunc.c in nc_open, but here the netCDF-4 part of opening a file
 * is handled. */
static int
nc4_open_file(const char *path, int mode, MPI_Comm comm,
	      MPI_Info info, NC_FILE_INFO_T *nc)
{
   hid_t fapl_id = H5P_DEFAULT;
   unsigned flags = (mode & NC_WRITE) ? 
      H5F_ACC_RDWR : H5F_ACC_RDONLY;
   int retval;

   LOG((3, "nc4_open_file: path %s mode %d", path, mode));
   assert(path && nc);

   /* Add necessary structs to hold netcdf-4 file data. */
   if ((retval = nc4_nc4f_list_add(nc, path, mode)))
      BAIL(retval);
   assert(nc->nc4_info && nc->nc4_info->root_grp);
   
   /* Need this access plist to control how HDF5 handles open onjects
    * on file close. (Setting H5F_CLOSE_SEMI will cause H5Fclose to
    * fail if there are any open objects in the file. */
   if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0)
      BAIL(NC_EHDFERR);
/*   if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_SEMI)) */
   if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_STRONG))
      BAIL(NC_EHDFERR);

#ifdef USE_PARALLEL
   /* If this is a parallel file create, set up the file creation
      property list. */
   if (mode & NC_MPIIO || mode & NC_MPIPOSIX)
   {
      nc->nc4_info->parallel++;
      if (mode & NC_MPIIO)  /* MPI/IO */
      {
	 LOG((4, "opening parallel file with MPI/IO"));
	 if (H5Pset_fapl_mpio(fapl_id, comm, info) < 0)
	    BAIL(NC_EPARINIT);
      }
      else /* MPI/POSIX */
      {
	 LOG((4, "opening parallel file with MPI/posix"));
	 if (H5Pset_fapl_mpiposix(fapl_id, comm, 0) < 0)
	    BAIL(NC_EPARINIT);
      }
   }
#endif /* USE_PARALLEL */
   
   if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) 
      BAIL(NC_EHDFERR);

   /* The NetCDF-3.x prototype contains an mode option NC_SHARE for
      multiple processes accessing the dataset concurrently.  As there
      is no HDF5 equivalent, NC_SHARE is treated as NC_NOWRITE. */
   if ((nc->nc4_info->hdfid = H5Fopen(path, flags, fapl_id)) < 0)
      BAIL(NC_EHDFERR);

/*    /\* Release the property list. *\/ */
/*    if (H5Pclose(fapl_id) < 0) */
/*       BAIL(NC_EPARINIT); */

   /* Does the mode specify that this file is read-only? */
   if (mode == NC_NOWRITE)
      nc->nc4_info->no_write++;

   /* Now read in all the metadata. Some types and dimscale
    * information may be difficult to resolve here, if, for example, a
    * dataset of user-defined type is encountered before the
    * definition of that type. */
   if ((retval = nc4_rec_read_metadata(nc->nc4_info->root_grp)))
      BAIL(retval);

   /* Now make sure that we've got a valid type for each variable. */
   if ((retval = nc4_rec_match_types(nc->nc4_info->root_grp)))
      BAIL(retval);

   /* Now figure out which netCDF dims are indicated by the dimscale
    * information. */
   if ((retval = nc4_rec_match_dimscales(nc->nc4_info->root_grp)))
      BAIL(retval);

#ifdef LOGGING
   /* This will print out the names, types, lens, etc of the vars and
      atts in the file, if the logging level is 2 or greater. */ 
   log_metadata_nc(nc);
#endif

   return NC_NOERR;

 exit:
   if (fapl_id != H5P_DEFAULT) H5Pclose(fapl_id);
   if (nc->nc4_info->hdfid > 0) H5Fclose(nc->nc4_info->hdfid);
   if (nc->nc4_info) nc_free(nc->nc4_info);
   return retval;
}

static int
nc_open_file(const char *path, int mode, int basepe, size_t *chunksizehintp, 
	     int use_parallel, MPI_Comm comm, MPI_Info info, int *ncidp)
{
   int hdf_file = 0;
   int res;
   
   assert(path && ncidp);
   LOG((1, "nc_open_file: path %s mode %d comm %d info %d", 
	path, mode, comm, info));

   /* If this is our first file, turn off HDF5 error messages. */
   if (virgin)
   {
      if (H5Eset_auto(NULL, NULL) < 0)
	 LOG((0, "Couldn't turn off HDF5 error messages!"));
      LOG((1, "HDF5 error messages turned off!"));
      virgin = 0;
   }

   /* Check the mode for validity. First make sure only certain bits
    * are turned on. Also MPI I/O and MPI POSIX cannot both be
    * selected at once. */
   if (mode & ~(NC_WRITE | NC_SHARE | NC_MPIIO | NC_MPIPOSIX | NC_LOCK) ||
       (mode & NC_MPIIO && mode & NC_MPIPOSIX))
      return NC_EINVAL;

   /* Figure out if this is a hdf5 file. */
   if ((res = nc_check_for_hdf5(path, use_parallel, comm, info, &hdf_file)))
      return res;

   /* Allocate the storage for this file info struct, and fill it with
      zeros. */
   if ((res = nc4_file_list_add(++last_file_id << ID_SHIFT)))
      return res;

   /* If this is a version 4 file, set the lib member to point at the
      struct of netcdf4 functions. Similarly for v3 files. Call the
      netcdf3 or netcdf4 nc__open, with parameters. */
   if (hdf_file)
   {
      nc_file->int_ncid = nc_file->ext_ncid;
      res = nc4_open_file(path, mode, comm, info, nc_file);
   }
   else /* netcdf */
   {
      res = nc3__open_mp(path, mode, basepe, chunksizehintp, 
			 &(nc_file->int_ncid));
   }

   /* If it succeeds, pass back the new ncid. Otherwise, remove this
      file from the list. */
   if (res)
   {
      nc4_file_list_del(nc_file);
      last_file_id--;
   }
   else
   {
      *ncidp = nc_file->ext_ncid;
      numfiles++;
   }

   return res;
}

int
nc__open_mp(const char *path, int mode, int basepe,
	    size_t *chunksizehintp, int *ncidp)
{
   return nc_open_file(path, mode, basepe, chunksizehintp, 0, 0, 0, ncidp);
}

/*#ifdef USE_PARALLEL*/
int
nc_open_par(const char *path, int mode, MPI_Comm comm, 
	    MPI_Info info, int *ncidp)
{
   /* Only netcdf-4 files can be parallel. */
   if (!mode & NC_NETCDF4)
      return NC_ENOTNC4;

   /* Must use either MPIIO or MPIPOSIX. Default to the former. */
   if (!(mode & NC_MPIIO || mode & NC_MPIPOSIX))
      mode |= NC_MPIIO;

   return nc_open_file(path, mode, 0, NULL, 1, comm, info, ncidp);
}
/*#endif*/ /* USE_PARALLEL */

int
nc_open(const char *path, int mode, int *ncidp)
{
   return nc_open_file(path, mode, 0, NULL, 0, 0, 0, ncidp);
}

int
nc__open(const char *path, int mode, 
	 size_t *chunksizehintp, int *ncidp)
{
   return nc_open_file(path, mode, 0, chunksizehintp, 0, 0, 0, ncidp);
}

/* Unfortunately HDF only allows specification of fill value only when
   a dataset is created. Whereas in netcdf, you first create the
   variable and then (optionally) specify the fill value. To
   accomplish this in HDF5 I have to delete the dataset, and recreate
   it, with the fill value specified. */
int 
nc_set_fill(int ncid, int fillmode, int *old_modep)
{
   NC_FILE_INFO_T *nc;
 
   LOG((2, "nc_set_fill: ncid 0x%x fillmode %d", ncid, fillmode));

   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* Is this a netcdf-3 file? */
   if (!nc->nc4_info)
      return nc3_set_fill(nc->int_ncid, fillmode, old_modep);

   /* Trying to set fill on a read-only file? You sicken me! */
   if (nc->nc4_info->no_write)
      return NC_EPERM;

   /* Did you pass me some weird fillmode? */
   if (fillmode != NC_FILL && fillmode != NC_NOFILL)
      return NC_EINVAL;

   /* If the user wants to know, tell him what the old mode was. */
   if (old_modep)
      *old_modep = nc->nc4_info->fill_mode;

   nc->nc4_info->fill_mode = fillmode;

   return NC_NOERR;
}

/* Put the file back in redef mode. This is done automatically for
 * netcdf-4 files, if the user forgets. */
int
nc_redef(int ncid)
{
   NC_FILE_INFO_T *nc;

   LOG((1, "nc_redef: ncid 0x%x", ncid));

   /* Find this file's metadata. */
   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* Handle netcdf-3 files. */
   if (!nc->nc4_info)
      return nc3_redef(nc->int_ncid);

   /* If we're already in define mode, return an error. */
   if (nc->nc4_info->flags & NC_INDEF)
      return NC_EINDEFINE;

   /* If the file is read-only, return an error. */
   if (nc->nc4_info->no_write)
      return NC_EPERM;

   /* Set define mode. */
   nc->nc4_info->flags |= NC_INDEF;

   /* For nc_abort, we need to remember if we're in define mode as a
      redef. */
   nc->nc4_info->redef++;

   return NC_NOERR;
}

/* For netcdf-4 files, this just calls nc_enddef, ignoring the extra
 * parameters. */
int
nc__enddef(int ncid, size_t h_minfree, size_t v_align,
	   size_t v_minfree, size_t r_align)
{
   NC_FILE_INFO_T *nc;

   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* Deal with netcdf-3 files one way, netcdf-4 another way.  */
   if (!nc->nc4_info)
      return nc3__enddef(nc->int_ncid, h_minfree, v_align, v_minfree, r_align);
   else
      return nc_enddef(ncid);
}

/* Take the file out of define mode. This is called automatically for
 * netcdf-4 files, if the user forgets. */
int
nc_enddef(int ncid)
{
   NC_FILE_INFO_T *nc;

   LOG((1, "nc_enddef: ncid 0x%x", ncid));

   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* Take care of netcdf-3 files. */
   if (!nc->nc4_info)
      return nc3_enddef(nc->int_ncid);

   return nc4_enddef_netcdf4_file(nc->nc4_info);
}

/* This function will write all changed metadata, and (someday) reread
 * all metadata from the file. */
static int
sync_netcdf4_file(NC_HDF5_FILE_INFO_T *h5)
{
   int retval;

   assert(h5);
   LOG((3, "sync_netcdf4_file"));

   /* If we're in define mode, that's an error, for strict nc3 rules,
    * otherwise, end define mode. */
   if (h5->flags & NC_INDEF)
   {
      if (h5->cmode & NC_CLASSIC_MODEL)
	 return NC_EINDEFINE;

      /* Turn define mode off. */
      h5->flags ^= NC_INDEF;
      
      /* Redef mode needs to be tracked seperately for nc_abort. */
      h5->redef = 0;
   }

#ifdef LOGGING
   /* This will print out the names, types, lens, etc of the vars and
      atts in the file, if the logging level is 2 or greater. */ 
   log_metadata_nc(h5->root_grp->file);
#endif

   /* Write any metadata that has changed. */
   if ((retval = nc4_rec_write_metadata(h5->root_grp)))
      return retval;

   H5Fflush(h5->hdfid, H5F_SCOPE_GLOBAL);

   /* Reread all the metadata. */
   /*if ((retval = nc4_rec_read_metadata(grp)))
     return retval;*/

   return retval;
}

/* Flushes all buffers associated with the file, after writing all
   changed metadata. This may only be called in data mode. */
int
nc_sync(int ncid)
{
   NC_FILE_INFO_T *nc;
   int retval;

   LOG((2, "nc_sync: ncid 0x%x", ncid));

   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* Take care of netcdf-3 files. */
   if (!nc->nc4_info)
      return nc3_sync(nc->int_ncid);

   /* If we're in define mode, we can't sync. */
   if (nc->nc4_info && nc->nc4_info->flags & NC_INDEF)
   {
      if (nc->nc4_info->cmode & NC_CLASSIC_MODEL)
	 return NC_EINDEFINE;
      if ((retval = nc_enddef(ncid)))
	 BAIL(retval);
   }

   return sync_netcdf4_file(nc->nc4_info);

  exit:
   return retval;
}

/* This function will free all allocated metadata memory, and close
   the HDF5 file. The group that is passed in must be the root group
   of the file. */
static int
close_netcdf4_file(NC_HDF5_FILE_INFO_T *h5, int abort)
{
   int retval;

   assert(h5 && h5->root_grp);
   LOG((3, "close_netcdf4_file: h5->path %s abort %d", 
	h5->path, abort));

   /* According to the docs, always end define mode on close. */
   if (h5->flags & NC_INDEF)
      h5->flags ^= NC_INDEF;

   /* Sync the file, unless we're aborting. */
   if (!abort)
      if ((retval = sync_netcdf4_file(h5)))
	 return retval;

   /* Delete all the list contents for vars, dims, and atts, in each
    * group. */
   nc4_rec_grp_del(&h5->root_grp, h5->root_grp);

   /* Close hdf file. */
   if (H5Fclose(h5->hdfid) < 0) 
   {
#ifdef LOGGING
      /* If the close doesn't work, probably there are still some HDF5
       * objects open, which means there's a bug in the library. So
       * print out some info on to help the poor programmer figure it
       * out. */
      {
	 int nobjs;
	 if ((nobjs = H5Fget_obj_count(h5->hdfid, H5F_OBJ_ALL) < 0))
	    return NC_EHDFERR;
	 LOG((0, "There are %d HDF5 objects open!", nobjs));
      }
#endif      
      return NC_EHDFERR;
   }

   /* Free the nc4_info struct. */
   nc_free(h5);
   return NC_NOERR;
}

/* From the netcdf-3 docs: The function nc_abort just closes the
   netCDF dataset, if not in define mode. If the dataset is being
   created and is still in define mode, the dataset is deleted. If
   define mode was entered by a call to nc_redef, the netCDF dataset
   is restored to its state before definition mode was entered and the
   dataset is closed. */
int
nc_abort(int ncid)
{
   NC_FILE_INFO_T *nc;
   int delete_file = 0;
   char path[NC_MAX_NAME + 1];
   int retval = NC_NOERR;

   LOG((2, "nc_abort: ncid 0x%x", ncid));

   /* Find metadata for this file. */
   if (!(nc = nc4_find_nc_file(ncid)))
      return NC_EBADID;

   /* If this is a netcdf-3 file, let the netcdf-3 library handle it. */
   if (!nc->nc4_info)
      return nc3_abort(nc->int_ncid);

   /* If we're in define mode, but not redefing the file, delete it. */
   if (nc->nc4_info->flags & NC_INDEF && !nc->nc4_info->redef)
   {
      delete_file++;
      strcpy(path, nc->nc4_info->path);
   }

   /* Free any resources the netcdf-4 library has for this file's
    * metadata. */
   if ((retval = close_netcdf4_file(nc->nc4_info, 1)))
      return retval;
   
   /* Delete the file, if we should. */
   if (delete_file)
      remove(path);

   /* Delete this entry from our list of open files. */
   nc4_file_list_del(nc);

   return retval;
}

/* Close the netcdf file, writing any changes first. */
int
nc_close(int ncid)
{
   NC_GRP_INFO_T *grp;
   NC_FILE_INFO_T *nc;
   NC_HDF5_FILE_INFO_T *h5;
   int retval;

   LOG((1, "nc_close: ncid 0x%x", ncid));

   /* Find our metadata for this file. */
   if ((retval = nc4_find_nc_grp_h5(ncid, &nc, &grp, &h5)))
      return retval;

   /* Call either the nc4 or nc3 close. */
   if (!h5)
   {
      if ((retval = nc3_close(nc->int_ncid)))
	 return retval;
   }
   else
   {
      nc = grp->file;
      assert(nc);
      
      /* This must be the root group. */
      if (grp->parent)
	 return NC_EBADGRPID;

      if ((retval = close_netcdf4_file(grp->file->nc4_info, 0)))
	 return retval;
   }

   /* Delete this entry from our list of open files. */
   nc4_file_list_del(nc);
   numfiles--;

#ifdef USE_PARALLEL
   /* If all files have been closed, close he HDF5 library. This will
    * clean up some MPI stuff that otherwise will be a problem when
    * the user calls MPI_Finalize. */
   if (!numfiles)
      if ((retval = H5close()) < 0)
	 return NC_EHDFERR;
#endif /* USE_PARALLEL */

   return NC_NOERR;
}

/* It's possible for any of these pointers to be NULL, in which case
   don't try to figure out that value. */
int
nc_inq(int ncid, int *ndimsp, int *nvarsp, int *nattsp, int *unlimdimidp)
{
   NC_FILE_INFO_T *nc;
   NC_HDF5_FILE_INFO_T *h5;
   NC_GRP_INFO_T *grp;
   NC_DIM_INFO_T *dim;
   NC_ATT_INFO_T *att;
   NC_VAR_INFO_T *var;
   int retval;

   LOG((2, "nc_inq: ncid 0x%x", ncid)); 

   /* Find file metadata. */
   if ((retval = nc4_find_nc_grp_h5(ncid, &nc, &grp, &h5)))
      return retval;

   /* Take care of netcdf-3 files. */
   if (!h5)
      return nc3_inq(nc->int_ncid, ndimsp, nvarsp, nattsp, unlimdimidp);

   /* Count the number of dims, vars, and global atts. */
   assert(h5 && grp && nc);
   if (ndimsp)
   {
      *ndimsp = 0;
      for (dim = grp->dim; dim; dim = dim->next)
	 (*ndimsp)++;
   }
   if (nvarsp)
   {
      *nvarsp = 0;
      for (var = grp->var; var; var= var->next)
	 (*nvarsp)++;
   }
   if (nattsp)
   {
      *nattsp = 0;
      for (att = grp->att; att; att = att->next)
	 (*nattsp)++;
   }

   if (unlimdimidp)
   {
      /* Default, no unlimited dimension */
      *unlimdimidp = -1;

      /* If there's more than one unlimited dim, which was not possible
	 with netcdf-3, then only the last unlimited one will be reported
	 back in xtendimp. */
      for (dim = grp->dim; dim; dim = dim->next)
	 if (dim->unlimited)
	    *unlimdimidp = dim->dimid;
   }

   return NC_NOERR;   
}

int 
nc_inq_ndims(int ncid, int *ndimsp)
{
   return nc_inq(ncid, ndimsp, NULL, NULL, NULL);
}

/* Find out how many vars there are in a file. */
int 
nc_inq_nvars(int ncid, int *nvarsp)
{
   return nc_inq(ncid, NULL, nvarsp, NULL, NULL);
}

/* Count the number of global attributes. */
int 
nc_inq_natts(int ncid, int *nattsp)
{
   return nc_inq(ncid, NULL, NULL, nattsp, NULL);
}

/* This function will do the enddef stuff for a netcdf-4 file. */
int
nc4_enddef_netcdf4_file(NC_HDF5_FILE_INFO_T *h5)
{
   assert(h5);
   LOG((3, "sync_netcdf4_file"));

   /* If we're not in define mode, return an error. */
   if (!(h5->flags & NC_INDEF))
      return NC_ENOTINDEFINE;

   /* Turn define mode off. */
   h5->flags ^= NC_INDEF;

   /* Redef mode needs to be tracked seperately for nc_abort. */
   h5->redef = 0;

   return sync_netcdf4_file(h5);
}


