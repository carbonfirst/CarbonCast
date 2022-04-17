/* This is part of the netCDF package.
   Copyright 2005 University Corporation for Atmospheric Research/Unidata
   See COPYRIGHT file for conditions of use.

   Test HDF5 file code. These are not intended to be exhaustive tests,
   but they use HDF5 the same way that netCDF-4 does, so if these
   tests don't work, than netCDF-4 won't work either.

   This program deals with HDF5 compound types.

   $Id: tst_h_compounds2.c,v 1.10 2008/05/30 17:23:26 ed Exp $
*/
#include <nc_tests.h>

#define FILE_NAME "tst_h_compounds2.h5"

int
main()
{
   printf("\n*** Checking HDF5 compound types some more.\n");
   printf("*** Checking HDF5 compound attribute which contains an array of unsigned byte...");
   {
#define DIM1_LEN 1
#define ATT_NAME "a1"
      struct s1
      {
	    unsigned char x[NC_MAX_NAME + 1];
	    float y;
      };
      struct s1 data_out[DIM1_LEN], data_in[DIM1_LEN];

      hid_t fileid, grpid, typeid, spaceid, array1_tid, attid, str_tid;
      hid_t fcpl_id, fapl_id;
      hsize_t dims[1] = {NC_MAX_NAME + 1};
      int i, j;

      /* Create some phony data. */   
      for (i = 0; i < DIM1_LEN; i++)
      {
	 for (j = 0; j < NC_MAX_NAME + 1; j++)
	    data_out[i].x[j] = j;
	 data_out[i].y = 99.99;
      }

      /* Set latest_format in access propertly list and
       * H5P_CRT_ORDER_TRACKED in the creation property list. This
       * turns on HDF5 creation ordering. */
      if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
/*   if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_SEMI)) ERR;*/
      if (H5Pset_fclose_degree(fapl_id, H5F_CLOSE_STRONG)) ERR;
      if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) ERR;
      if ((fcpl_id = H5Pcreate(H5P_FILE_CREATE)) < 0) ERR;
      if (H5Pset_link_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED |
					       H5P_CRT_ORDER_INDEXED)) < 0) ERR;
      if (H5Pset_attr_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED |
					       H5P_CRT_ORDER_INDEXED)) < 0) ERR;

      /* Open file and get root group. */
      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, fcpl_id, fapl_id)) < 0) ERR;
      if ((grpid = H5Gopen(fileid, "/")) < 0) ERR;

      /* Create a compound type. */
      if ((typeid = H5Tcreate(H5T_COMPOUND, sizeof(struct s1))) < 0) ERR;
      str_tid = H5T_NATIVE_UCHAR;
/*	if ((str_tid = H5Tcopy(H5T_C_S1)) < 0) ERR;*/
/*      if (H5Tset_strpad(str_tid, H5T_STR_NULLTERM) < 0) ERR;*/
      if ((array1_tid = H5Tarray_create2(str_tid, 1, dims)) < 0) ERR;
/*      printf("sizeof(struct s1)=%d HOFFSET(struct s1, x) = %d HOFFSET(struct s1, y) = %d\n", 
	sizeof(struct s1), HOFFSET(struct s1, x), HOFFSET(struct s1, y));*/
      if (H5Tinsert(typeid, "x", HOFFSET(struct s1, x), array1_tid) < 0) ERR;
      if (H5Tinsert(typeid, "y", HOFFSET(struct s1, y), H5T_NATIVE_FLOAT) < 0) ERR;
      if (H5Tcommit(grpid, "c", typeid) < 0) ERR;

      /* Create a space. */
      dims[0] = DIM1_LEN;
      if ((spaceid = H5Screate_simple(1, dims, dims)) < 0) ERR;

      /* Create an attribute of this compound type. */
      if ((attid = H5Acreate2(grpid, ATT_NAME, typeid, spaceid, H5P_DEFAULT, H5P_DEFAULT)) < 0) ERR;

      /* Write some data. */
      if (H5Awrite(attid, typeid, data_out) < 0) ERR;
      
      /* Release all resources. */
      if (H5Aclose(attid) < 0 ||
	  H5Tclose(array1_tid) < 0 ||
	  H5Tclose(typeid) < 0 ||
/*	  H5Tclose(str_tid) < 0 ||*/
	  H5Sclose(spaceid) < 0 ||
	  H5Gclose(grpid) < 0 ||
	  H5Fclose(fileid) < 0) ERR;

      /* Now open the file and read it. */
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDONLY, H5P_DEFAULT)) < 0) ERR;
      if ((grpid = H5Gopen(fileid, "/")) < 0) ERR;
      if ((attid = H5Aopen_by_name(grpid, ".", ATT_NAME, H5P_DEFAULT, H5P_DEFAULT)) < 0) ERR;
      if ((typeid = H5Aget_type(attid)) < 0) ERR;
      if (H5Tget_class(typeid) != H5T_COMPOUND) ERR;
      if (H5Aread(attid, typeid, data_in) < 0) ERR;

      /* Check the data. */
      for (i = 0; i < DIM1_LEN; i++)
	 if (strcmp((char *)data_out[i].x, (char *)data_in[i].x) ||
	     data_out[i].y != data_in[i].y) ERR;

      /* Release all resources. */
      if (H5Aclose(attid) < 0 ||
	  H5Tclose(typeid) < 0 ||
	  H5Gclose(grpid) < 0 ||
	  H5Fclose(fileid) < 0) ERR;
   }

   SUMMARIZE_ERR;
   FINAL_RESULTS;
}
