/* This is part of the netCDF package.
   Copyright 2005 University Corporation for Atmospheric Research/Unidata
   See COPYRIGHT file for conditions of use.

   Test HDF5 file code. These are not intended to be exhaustive tests,
   but they use HDF5 the same way that netCDF-4 does, so if these
   tests don't work, than netCDF-4 won't work either.

   $Id: tst_h_files.c,v 1.9 2008/04/23 17:01:34 ed Exp $
*/
#include <config.h>
#include <nc_tests.h>
#include "netcdf.h"

#define FILE_NAME "tst_h_files.h5"
#define GRP_NAME "Dectectives"

int
main()
{
   printf("\n*** Checking HDF5 file functions.\n");
   printf("*** Checking HDF5 file creates and opens...");
#define OPAQUE_SIZE 20
#define OPAQUE_NAME "type"
#define ATT_NAME "att_name"
#define DIM_LEN 3
   {
      hid_t fileid, access_plist, typeid, spaceid, attid, fapl_id, grpid;
      hsize_t dims[1]; /* netcdf attributes always 1-D. */
      unsigned char data[DIM_LEN][OPAQUE_SIZE];
      hsize_t num_obj, i;
      int obj_class;
      char obj_name[NC_MAX_NAME + 1];
      H5T_class_t class;
      size_t type_size = 0;

      /* Set the access list so that closes will fail if something is
       * still open in the file. */
      if ((access_plist = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      if (H5Pset_fclose_degree(access_plist, H5F_CLOSE_SEMI)) ERR;

      /* Create file. */
      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, H5P_DEFAULT, 
			      access_plist)) < 0) ERR;
      /* Add an opaque type. */
      if ((typeid = H5Tcreate(H5T_OPAQUE, OPAQUE_SIZE)) < 0) ERR;
      if (H5Tcommit(fileid, OPAQUE_NAME, typeid) < 0) ERR;
      
      /* Add attribute of this type. */
      dims[0] = 3;
      if ((spaceid = H5Screate_simple(1, dims, NULL)) < 0) ERR;
      if ((attid = H5Acreate(fileid, ATT_NAME, typeid, spaceid, 
			     H5P_DEFAULT)) < 0) ERR;
      if (H5Awrite(attid, typeid, data) < 0) ERR;

      if (H5Aclose(attid) < 0) ERR;
      if (H5Tclose(typeid) < 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;

      if (H5Eset_auto(NULL, NULL) < 0) ERR;

      /* Reopen the file. */
      if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      /*if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_SEMI)) ERR;*/
      if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_STRONG)) ERR;
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, fapl_id)) < 0) ERR;
      if ((grpid = H5Gopen(fileid, "/")) < 0) ERR;

      if (H5Gget_num_objs(grpid, &num_obj) < 0) ERR;
      for (i = 0; i < num_obj; i++)
      {
	 if ((obj_class = H5Gget_objtype_by_idx(grpid, i)) < 0) ERR;
	 if (H5Gget_objname_by_idx(grpid, i, obj_name, 
				   NC_MAX_NAME) < 0) ERR;
	 if (obj_class != H5G_TYPE) ERR;
	 if ((typeid = H5Topen(grpid, obj_name)) < 0) ERR;
	 if ((class = H5Tget_class(typeid)) < 0) ERR;
	 if (class != H5T_OPAQUE) ERR;
	 if (!(type_size = H5Tget_size(typeid))) ERR;
      }

      /* Close everything. */
      if (H5Pclose(access_plist)) ERR;
      if (H5Gclose(grpid) < 0) ERR;
      /*if (H5Tclose(typeid) < 0) ERR;*/
      if (H5Fclose(fileid) < 0) ERR;

      if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_SEMI)) ERR;
      if ((fileid = H5Fopen(FILE_NAME, 0, fapl_id)) < 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;

   }
   SUMMARIZE_ERR;

   printf("*** Checking HDF5 file creates and opens some more...");
   {
      int objs;
      hid_t fileid, fileid2, grpid, access_plist;


      /* Set the access list so that closes will fail if something is
       * still open in the file. */
      if ((access_plist = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      if (H5Pset_fclose_degree(access_plist, H5F_CLOSE_SEMI)) ERR;

      /* Create file and create group. */
      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, H5P_DEFAULT, 
			      access_plist)) < 0) ERR;
      if ((grpid = H5Gcreate(fileid, GRP_NAME, 0)) < 0) ERR;

      /* How many open objects are there? */
      if ((objs = H5Fget_obj_count(fileid, H5F_OBJ_ALL)) < 0) ERR;
      if (objs != 2) ERR;
      if ((objs = H5Fget_obj_count(fileid, H5F_OBJ_GROUP)) < 0) ERR;
      if (objs != 1) ERR;

      /* Turn off HDF5 error messages. */
      if (H5Eset_auto(NULL, NULL) < 0) ERR;

      /* This H5Fclose should fail, because I didn't close the group. */
      if (H5Fclose(fileid) >= 0) ERR;

      /* Now close the group first, and then the file. */
      if (H5Gclose(grpid) < 0 ||
	  H5Fclose(fileid) < 0) ERR;

      /* Now create the file again, to make sure that it really is not
       * just mearly dead, but really most sincerely dead. */
      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, H5P_DEFAULT, 
			      access_plist)) < 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;

      /* Confirm that the same file can be opened twice at the same time,
       * for read only access. */
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, H5P_DEFAULT)) < 0) ERR;
      if ((fileid2 = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, H5P_DEFAULT)) < 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;
      if (H5Fclose(fileid2) < 0) ERR;

      /* Once open for read only access, the file can't be opened again
       * for write access. */
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, H5P_DEFAULT)) < 0) ERR;
      if ((fileid2 = H5Fopen(FILE_NAME, H5F_ACC_RDWR, H5P_DEFAULT)) >= 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;

      /* But you can open the file for read/write access, and then open
       * it again for read only access. */
      if ((fileid2 = H5Fopen(FILE_NAME, H5F_ACC_RDWR, H5P_DEFAULT)) < 0) ERR;
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, H5P_DEFAULT)) < 0) ERR;
      if (H5Fclose(fileid) < 0) ERR;
      if (H5Fclose(fileid2) < 0) ERR;
   }
   SUMMARIZE_ERR;

   printf("*** Creating file...");
   {
#define VAR_NAME "HALs_memory"
#define NDIMS 1
#define DIM1_LEN 40000
#define SC 10000 /* slice count. */
#define MILLION 1000000

      hid_t fileid, write_spaceid, datasetid, mem_spaceid;
      hsize_t start[NDIMS], count[NDIMS];
      hsize_t dims[1];
      int *data;
      int num_steps;
      int i, s;

      /* We will write the same slice of random data over and over to
       * fill the file. */
      if (!(data = malloc(SC * sizeof(int))))
	 ERR_RET;
      for (i = 0; i < SC; i++)
	 data[i] = rand();
      
      /* Create file. */
      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, H5P_DEFAULT, 
			      H5P_DEFAULT)) < 0) ERR;

      /* Create a space to deal with one slice in memory. */
      dims[0] = SC;
      if ((mem_spaceid = H5Screate_simple(NDIMS, dims, NULL)) < 0) ERR;

      /* Create a space to write all slices. */
      dims[0] = DIM1_LEN;
      if ((write_spaceid = H5Screate_simple(NDIMS, dims, NULL)) < 0) ERR;

      /* Create dataset. */
      if ((datasetid = H5Dcreate1(fileid, VAR_NAME, H5T_NATIVE_INT, 
				  write_spaceid, H5P_DEFAULT)) < 0) ERR;

      /* Write the data in num_step steps. */
      num_steps = DIM1_LEN/SC;
      count[0] = SC;
      for (s = 0; s < num_steps; s++)
      {
	 /* Select hyperslab for write of one slice. */
	 start[0] = s * SC;
	 if (H5Sselect_hyperslab(write_spaceid, H5S_SELECT_SET, 
				 start, NULL, count, NULL) < 0) ERR;

	 if (H5Dwrite(datasetid, H5T_NATIVE_INT, mem_spaceid, write_spaceid, 
		      H5P_DEFAULT, data) < 0) ERR;
      }
      
      /* Close. */
      free(data);
      if (H5Dclose(datasetid) < 0 ||
	  H5Sclose(write_spaceid) < 0 ||
	  H5Sclose(mem_spaceid) < 0 ||
	  H5Fclose(fileid) < 0)
	 ERR;
   }
   SUMMARIZE_ERR;
   FINAL_RESULTS;
}
