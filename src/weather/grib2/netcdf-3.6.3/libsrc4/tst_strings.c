/* This is part of the netCDF package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   Test netcdf-4 string types.

   $Id: tst_strings.c,v 1.26 2008/04/23 17:01:34 ed Exp $
*/

#include <config.h>
#include "netcdf.h"
#include <nc_tests.h>

#define FILE_NAME "tst_strings.nc"
#define DIM_LEN 9
#define ATT_NAME "measure_for_measure_att"
#define DIM_NAME "line"
#define VAR_NAME "measure_for_measure_var"
#define NDIMS 1

int
main(int argc, char **argv)
{
#ifdef USE_PARALLEL
   MPI_Init(&argc, &argv);
#endif

   printf("\n*** Testing netcdf-4 string type.\n");
   printf("*** testing string variable...");
   {
      int var_dimids[NDIMS];
      int ndims, nvars, natts, unlimdimid;
      nc_type var_type;
      char var_name[NC_MAX_NAME + 1];
      int var_natts, var_ndims;
      int ncid, varid, i, dimids[NDIMS];
      char *data_in[DIM_LEN];
      char *data[DIM_LEN] = {"Let but your honour know",
			     "Whom I believe to be most strait in virtue", 
			     "That, in the working of your own affections", 
			     "Had time cohered with place or place with wishing", 
			     "Or that the resolute acting of your blood",
			     "Could have attain'd the effect of your own purpose",
			     "Whether you had not sometime in your life",
			     "Err'd in this point which now you censure him", 
			     "And pull'd the law upon you."};
   
      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR;
      if (nc_def_dim(ncid, DIM_NAME, DIM_LEN, dimids)) ERR;
      if (nc_def_var(ncid, VAR_NAME, NC_STRING, NDIMS, dimids, &varid)) ERR;
      if (nc_inq(ncid, &ndims, &nvars, &natts, &unlimdimid)) ERR;
      if (ndims != NDIMS || nvars != 1 || natts != 0 || unlimdimid != -1) ERR;
      if (nc_inq_var(ncid, varid, var_name, &var_type, &var_ndims,
		     var_dimids, &var_natts)) ERR;
      if (var_type != NC_STRING || strcmp(var_name, VAR_NAME) || var_ndims != NDIMS ||
	  var_dimids[0] != dimids[0]) ERR;
      if (nc_put_var(ncid, varid, data)) ERR;
      if (nc_close(ncid)) ERR;
      
      /* Check it out. */
      if (nc_open(FILE_NAME, NC_NOWRITE, &ncid)) ERR;
      if (nc_inq(ncid, &ndims, &nvars, &natts, &unlimdimid)) ERR;
      if (ndims != NDIMS || nvars != 1 || natts != 0 || unlimdimid != -1) ERR;
      if (nc_inq_var(ncid, varid, var_name, &var_type, &var_ndims,
		     var_dimids, &var_natts)) ERR;
      if (var_type != NC_STRING || strcmp(var_name, VAR_NAME) || var_ndims != NDIMS ||
	  var_dimids[0] != dimids[0]) ERR;
      if (nc_get_var(ncid, varid, data_in)) ERR;
      for (i=0; i<DIM_LEN; i++)
	 if (strcmp(data_in[i], data[i])) ERR;
      for (i = 0; i < DIM_LEN; i++)
	 free(data_in[i]);
      if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;
   printf("*** testing string attribute...");
   {
      
      size_t att_len;
      int ndims, nvars, natts, unlimdimid;
      nc_type att_type;
      int ncid, i;
      char *data_in[DIM_LEN];
      char *data[DIM_LEN] = {"Let but your honour know",
			     "Whom I believe to be most strait in virtue", 
			     "That, in the working of your own affections", 
			     "Had time cohered with place or place with wishing", 
			     "Or that the resolute acting of your blood",
			     "Could have attain'd the effect of your own purpose",
			     "Whether you had not sometime in your life",
			     "Err'd in this point which now you censure him", 
			     "And pull'd the law upon you."};
   

      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR;
      if (nc_put_att(ncid, NC_GLOBAL, ATT_NAME, NC_STRING, DIM_LEN, data)) ERR;
      if (nc_inq(ncid, &ndims, &nvars, &natts, &unlimdimid)) ERR;
      if (ndims != 0 || nvars != 0 || natts != 1 || unlimdimid != -1) ERR;
      if (nc_inq_att(ncid, NC_GLOBAL, ATT_NAME, &att_type, &att_len)) ERR;
      if (att_type != NC_STRING || att_len != DIM_LEN) ERR;
      if (nc_close(ncid)) ERR;
      
      /* Check it out. */
      if (nc_open(FILE_NAME, NC_NOWRITE, &ncid)) ERR;
      if (nc_inq(ncid, &ndims, &nvars, &natts, &unlimdimid)) ERR;
      if (ndims != 0 || nvars != 0 || natts != 1 || unlimdimid != -1) ERR;
      if (nc_inq_att(ncid, NC_GLOBAL, ATT_NAME, &att_type, &att_len)) ERR;
      if (att_type != NC_STRING || att_len != DIM_LEN) ERR;
      if (nc_get_att(ncid, NC_GLOBAL, ATT_NAME, data_in)) ERR; 
      for (i = 0; i < att_len; i++)
	 if (strcmp(data_in[i], data[i])) ERR;
      if (nc_free_string(att_len, (char **)data_in)) ERR;
      if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;
   printf("*** testing string var functions...");

   {
#define MOBY_LEN 16
      int ncid, varid, i, dimids[NDIMS];
      char *data[] = {"Perhaps a very little thought will now enable you to account for ",
		      "those repeated whaling disasters--some few of which are casually ",
		      "chronicled--of this man or that man being taken out of the boat by ",
		      "the line, and lost.",
		      "For, when the line is darting out, to be seated then in the boat, ",
		      "is like being seated in the midst of the manifold whizzings of a ",
		      "steam-engine in full play, when every flying beam, and shaft, and wheel, ",
		      "is grazing you.",
		      "It is worse; for you cannot sit motionless in the heart of these perils, ",
		      "because the boat is rocking like a cradle, and you are pitched one way and ",
		      "the other, without the slightest warning;",
		      "But why say more?",
		      "All men live enveloped in whale-lines.",
		      "All are born with halters round their necks; but it is only when caught ",
		      "in the swift, sudden turn of death, that mortals realize the silent, subtle, ",
		      "ever-present perils of life."};
      char *data_in[MOBY_LEN];

      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR;
      if (nc_def_dim(ncid, DIM_NAME, MOBY_LEN, dimids)) ERR;
      if (nc_def_var(ncid, VAR_NAME, NC_STRING, NDIMS, dimids, &varid)) ERR;
      if (nc_put_var_string(ncid, varid, (const char **)data)) ERR;
      if (nc_close(ncid)) ERR;
      
      /* Check it out. */
     if (nc_open(FILE_NAME, NC_NOWRITE, &ncid)) ERR;
     if (nc_get_var_string(ncid, varid, data_in)) ERR;
     for (i=0; i<MOBY_LEN; i++)
	if (strcmp(data_in[i], data[i])) ERR;
     if (nc_free_string(MOBY_LEN, (char **)data_in)) ERR;
     if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;

   printf("*** testing string attributes...");
   {
#define SOME_PRES 16
#define NDIMS_PRES 1
#define ATT2_NAME "presidents"

      int ncid, i;
      char *data[SOME_PRES] = {"Washington", "Adams", "Jefferson", "Madison",
			       "Monroe", "Adams", "Jackson", "VanBuren",
			       "Harrison", "Tyler", "Polk", "Tayor", 
			       "Fillmore", "Peirce", "Buchanan", "Lincoln"};
      char *data_in[SOME_PRES];

      /* Create a file with string attribute. */
      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR;
      if (nc_put_att_string(ncid, NC_GLOBAL, ATT2_NAME, SOME_PRES, (const char **)data)) ERR;
      if (nc_close(ncid)) ERR;
      
      /* Check it out. */
      if (nc_open(FILE_NAME, NC_NOWRITE, &ncid)) ERR;
      if (nc_get_att_string(ncid, NC_GLOBAL, ATT2_NAME, (char **)data_in)) ERR;
      for (i=0; i < SOME_PRES; i++)
	 if (strcmp(data_in[i], data[i])) ERR;
      
      /* Must free your data! */
      if (nc_free_string(SOME_PRES, (char **)data_in)) ERR;

      if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;
   printf("*** testing string fill value...");

   {
#define NUM_PRES 43
#define SOME_PRES 16
#define NDIMS_PRES 1

      int ncid, varid, i, dimids[NDIMS_PRES];
      size_t start[NDIMS_PRES], count[NDIMS_PRES];
      char *data[SOME_PRES] = {"Washington", "Adams", "Jefferson", "Madison",
			       "Monroe", "Adams", "Jackson", "VanBuren",
			       "Harrison", "Tyler", "Polk", "Tayor", 
			       "Fillmore", "Peirce", "Buchanan", "Lincoln"};
      char *data_in[NUM_PRES];

      /* Create a file with NUM_PRES strings, and write SOME_PRES of
       * them. */
      /*      nc_set_log_level(4);*/
      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR;
      if (nc_def_dim(ncid, DIM_NAME, NUM_PRES, dimids)) ERR;
      if (nc_def_var(ncid, VAR_NAME, NC_STRING, NDIMS_PRES, dimids, &varid)) ERR;
      start[0] = 0;
      count[0] = SOME_PRES;
      if (nc_put_vara_string(ncid, varid, start, count, (const char **)data)) ERR;
      if (nc_close(ncid)) ERR;
      
      /* Check it out. */
      if (nc_open(FILE_NAME, NC_NOWRITE, &ncid)) ERR;
      if (nc_get_var_string(ncid, varid, data_in)) ERR;
      for (i=0; i < NUM_PRES; i++)
      {
	 if (i < SOME_PRES && strcmp(data_in[i], data[i])) ERR;
	 if (i >= SOME_PRES && strcmp(data_in[i], "")) ERR;
      }
      
      /* Must free your data! */
      if (nc_free_string(SOME_PRES, (char **)data_in)) ERR;

      if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;
   FINAL_RESULTS;
#ifdef USE_PARALLEL
   MPI_Finalize();
#endif   
}

