/* This is part of the netCDF package.
   Copyright 2005 University Corporation for Atmospheric Research/Unidata
   See COPYRIGHT file for conditions of use.

   Test netcdf-4 compound type feature. 

   $Id: tst_compounds2.c,v 1.2 2008/04/23 17:01:35 ed Exp $
*/

#include <config.h>
#include <stdlib.h>
#include "netcdf.h"
#include <nc_tests.h>

#define FILE_NAME "tst_compounds2.nc"

int
main(int argc, char **argv)
{

#ifdef USE_PARALLEL
   MPI_Init(&argc, &argv);
#endif

#ifdef EXTRA_TESTS
/*    printf("\n*** Testing netcdf-4 user defined type functions, even more.\n"); */
/*    printf("*** testing compound var containing byte arrays of various size..."); */
   {
#define DIM1_LEN 1      
#define ARRAY_LEN (NC_MAX_NAME + 1)
      int ncid;
      size_t len;
      nc_type xtype, type_id;
      int dim_sizes[] = {ARRAY_LEN};
      int i, j;

      struct s1
      {
	    unsigned char x[ARRAY_LEN];
	    float y;
      };
      struct s1 data_out[DIM1_LEN], data_in[DIM1_LEN];

      printf("array len=%d... ", ARRAY_LEN);

      /* Create some phony data. */   
      for (i = 0; i < DIM1_LEN; i++)
      {
	 data_out[i].y = 99.99;
	 for (j = 0; j < ARRAY_LEN; j++)
	    data_out[i].x[j] = j;
      }

/*      nc_set_log_level(5);*/
      /* Create a file with a nested compound type attribute and variable. */
      if (nc_create(FILE_NAME, NC_NETCDF4, &ncid)) ERR; 

      /* Now define the compound type. */
      printf("sizeof(struct s1)=%d\n", sizeof(struct s1));
      if (nc_def_compound(ncid, sizeof(struct s1), "c", &type_id)) ERR;
      if (nc_insert_array_compound(ncid, type_id, "x",
				   NC_COMPOUND_OFFSET(struct s1, x), NC_UBYTE, 1, dim_sizes)) ERR;
      if (nc_insert_compound(ncid, type_id, "y",
			     NC_COMPOUND_OFFSET(struct s1, y), NC_FLOAT)) ERR;

      /* Write it as an attribute. */
      if (nc_put_att(ncid, NC_GLOBAL, "a1", type_id, DIM1_LEN, data_out)) ERR;
      if (nc_close(ncid)) ERR;
      nc_set_log_level(0);

      /* Read the att and check values. */
      if (nc_open(FILE_NAME, NC_WRITE, &ncid)) ERR;
      if (nc_get_att(ncid, NC_GLOBAL, "a1", data_in)) ERR;
      for (i=0; i<DIM1_LEN; i++)
      {
	 if (data_in[i].y != data_out[i].y) ERR;
	 for (j = 0; j < ARRAY_LEN; j++)
	    if (data_in[i].x[j] != data_out[i].x[j]) ERR;
      }
      
      /* Use the inq functions to learn about the compound type. */
      if (nc_inq_att(ncid, NC_GLOBAL, "a1", &xtype, &len)) ERR;
      if (len != DIM1_LEN) ERR;
      
      /* Finish checking the containing compound type. */
      if (nc_close(ncid)) ERR;
   }

   SUMMARIZE_ERR;
#endif
   FINAL_RESULTS;
#ifdef USE_PARALLEL
   MPI_Finalize();
#endif   
}


