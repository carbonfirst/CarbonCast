/* This is part of the netCDF package.
   Copyright 2005 University Corporation for Atmospheric Research/Unidata
   See COPYRIGHT file for conditions of use.

   Test HDF5 file code. These are not intended to be exhaustive tests,
   but they use HDF5 the same way that netCDF-4 does, so if these
   tests don't work, than netCDF-4 won't work either.

   This file deals with HDF5 attributes, but more so.

   $Id: tst_h_atts2.c,v 1.6 2008/01/25 20:03:08 ed Exp $
*/
#include <nc_tests.h>
#include <H5DSpublic.h>

#define FILE_NAME "tst_h_atts2.h5"
#define MAX_LEN 80
#define DIM2_LEN 2

/* I am adding this test because of a weird attribute ordering bug in
 * netcdf-4 which I can't figure it out. So I'll test the HDF5
 * calls... */
int
main()
{
   printf("\n*** Checking HDF5 attribute functions.\n");
   printf("*** Checking HDF5 attribute ordering some more...");
   {
      hid_t fileid, grpid, attid, spaceid, dimscaleid, att_spaceid;
      hid_t fcpl_id, fapl_id;
      hsize_t num_obj, dims[1];
      char obj_name[MAX_LEN + 1];
      char att_name[3][20] = {"first", "second", "third"};
      signed char b[DIM2_LEN] = {-127, 126};
      int i;

      /* The test in this file fails on the HDF5 1.8.0 alpha releases, so
       * far, but is expected to succeed eventually. This macro allows
       * this test to be turned off so that life can move forward while
       * we wait for these HDF5 attribute ordering issues to be
       * resolved. */
/* #ifdef HDF5_ALPHA_RELEASE */
/*       printf("*** These tests turned off for HDF5 alpha releases.\n"); */
/*       return 0; */
/* #endif  */

      /* Create a file and get it's root group. */
      if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) ERR;
      if ((fcpl_id = H5Pcreate(H5P_FILE_CREATE)) < 0) ERR;
      if (H5Pset_link_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED |
					       H5P_CRT_ORDER_INDEXED)) < 0) ERR;

      if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, fcpl_id, fapl_id)) < 0) ERR;
      if ((grpid = H5Gopen(fileid, "/")) < 0) ERR;

      /* Write two group-level attributes containing byte attays of
       * length 2, call them "first" and "second". */
      dims[0] = DIM2_LEN;
      if ((att_spaceid = H5Screate_simple(1, dims, dims)) < 0) ERR;
      if ((attid = H5Acreate(grpid, att_name[0], H5T_NATIVE_UCHAR,
			     att_spaceid, H5P_DEFAULT)) < 0) ERR;
      if (H5Awrite(attid, H5T_NATIVE_UCHAR, b) < 0) ERR;
      if (H5Aclose(attid) < 0) ERR;
      if ((attid = H5Acreate(grpid , att_name[1], H5T_NATIVE_UCHAR,
			     att_spaceid, H5P_DEFAULT)) < 0) ERR;
      if (H5Awrite(attid, H5T_NATIVE_UCHAR, b) < 0) ERR;
      if (H5Aclose(attid) < 0) ERR;

      /* Create a dataset which will be a HDF5 dimension scale. */
      dims[0] = 1;
      if ((spaceid = H5Screate_simple(1, dims, dims)) < 0) ERR;
      if ((dimscaleid = H5Dcreate(grpid, "D1", H5T_IEEE_F32BE,
				  spaceid, H5P_DEFAULT)) < 0)
	 ERR;
      
      /* Indicate that this is a scale. */
      if (H5DSset_scale(dimscaleid, NULL) < 0) ERR;
      
      /* Add another attribute to the group. Call it "third". */
      if ((attid = H5Acreate(grpid , att_name[2], H5T_NATIVE_UCHAR,
			     att_spaceid, H5P_DEFAULT)) < 0) ERR;
      if (H5Awrite(attid, H5T_NATIVE_UCHAR, b) < 0) ERR;
      if (H5Aclose(attid) < 0) ERR;

      if (H5Dclose(dimscaleid) < 0 ||
	  H5Sclose(spaceid) < 0 ||
	  H5Sclose(att_spaceid) < 0 ||
	  H5Gclose(grpid) < 0 ||
	  H5Fclose(fileid) < 0) ERR;

      /* Now open the file and check. Magically, the attributes "second"
       * and "first" will be out of order. This can be checked with
       * h5dump, or with the following code, which will fail if it does
       * not find three attributes, in order "first", "second", and
       * "third". */

      /* Open file, group. */
      if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR;
      if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) ERR;
      if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDWR,
			    fapl_id)) < 0) ERR;
      if ((grpid = H5Gopen(fileid, "/")) < 0) ERR;

      /* How many attributes are there? */
      if ((num_obj = H5Aget_num_attrs(grpid)) != 3) ERR;
      
      /* Make sure the names are in the correct order. */
      for (i = 0; i < num_obj; i++)
      {
	 if ((attid = H5Aopen_idx(grpid, (unsigned int)i)) < 0) ERR;
	 if (H5Aget_name(attid, MAX_LEN + 1, obj_name) < 0) ERR;
	 if (H5Aclose(attid) < 0) ERR;
	 if (strcmp(obj_name, att_name[i])) ERR;
      }

      if (H5Gclose(grpid) < 0 ||
	  H5Fclose(fileid) < 0) ERR;
   }

   SUMMARIZE_ERR;
   printf("*** Checking HDF5 attribute ordering with 9 attributes...(skipping for HDF5 1.8.0 beta1)");
/* #define NUM_SIMPLE_ATTS 9 */
/* #define ATT_MAX_NAME 2 */
/*    { */
/*       hid_t fileid, grpid, attid, att_spaceid; */
/*       hsize_t num_obj; */
/*       char obj_name[MAX_LEN + 1]; */
/*       char name[NUM_SIMPLE_ATTS][ATT_MAX_NAME + 1] = {"Gc", "Gb", "Gs", "Gi", "Gf",  */
/* 						      "Gd", "G7", "G8", "G9"}; */
/*       hid_t fcpl_id, fapl_id; */
/*       int i; */

/*       /\* Set up property lists to turn on creation ordering. *\/ */
/*       if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR; */
/*      if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) ERR;*/
/*       if ((fcpl_id = H5Pcreate(H5P_FILE_CREATE)) < 0) ERR; */
/*       if (H5Pset_link_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED | */
/* 					       H5P_CRT_ORDER_INDEXED)) < 0) ERR; */
/*       if (H5Pset_attr_creation_order(fcpl_id, (H5P_CRT_ORDER_TRACKED | */
/* 					       H5P_CRT_ORDER_INDEXED)) < 0) ERR; */


/*       /\* Create a file and get it's root group. *\/ */
/*       if ((fileid = H5Fcreate(FILE_NAME, H5F_ACC_TRUNC, fcpl_id, fapl_id)) < 0) ERR; */
/*       if ((grpid = H5Gopen(fileid, "/")) < 0) ERR; */

/*       /\* These will all be zero-length atts. *\/ */
/*       if ((att_spaceid = H5Screate(H5S_NULL)) < 0) ERR; */

/*       for (i = 0; i < NUM_SIMPLE_ATTS; i++) */
/*       { */
/* 	 if ((attid = H5Acreate(grpid, name[i], H5T_NATIVE_INT, */
/* 				att_spaceid, H5P_DEFAULT)) < 0) ERR; */
/* 	 if (H5Aclose(attid) < 0) ERR; */
/*       } */

/*       if (H5Sclose(att_spaceid) < 0 || */
/* 	  H5Gclose(grpid) < 0 || */
/* 	  H5Fclose(fileid) < 0) ERR; */

/*       /\* Now open the file and check. *\/ */

/*       /\* Open file, group. *\/ */
/*       if ((fapl_id = H5Pcreate(H5P_FILE_ACCESS)) < 0) ERR; */
/*      if (H5Pset_libver_bounds(fapl_id, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST) < 0) ERR;*/
/*       if ((fileid = H5Fopen(FILE_NAME, H5F_ACC_RDWR, */
/* 			    fapl_id)) < 0) ERR; */
/*       if ((grpid = H5Gopen(fileid, "/")) < 0) ERR; */

/*       /\* How many attributes are there? *\/ */
/*       if ((num_obj = H5Aget_num_attrs(grpid)) != NUM_SIMPLE_ATTS) ERR; */
      
/*       /\* Make sure the names are in the correct order. *\/ */
/*       for (i = 0; i < num_obj; i++) */
/*       { */
/* 	 if ((attid = H5Aopen_idx(grpid, (unsigned int)i)) < 0) ERR; */
/* 	 if (H5Aget_name(attid, MAX_LEN + 1, obj_name) < 0) ERR; */
/* 	 if (H5Aclose(attid) < 0) ERR; */
/* 	 if (strcmp(obj_name, name[i])) ERR; */
/*       } */

/*       if (H5Gclose(grpid) < 0 || */
/* 	  H5Fclose(fileid) < 0) ERR; */
/*    } */

   SUMMARIZE_ERR;
   FINAL_RESULTS;
}
