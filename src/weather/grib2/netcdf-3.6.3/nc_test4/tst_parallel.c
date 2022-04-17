/* This is a quickie tester for netcdf-4. 
   $Id: tst_parallel.c,v 1.4 2005/10/20 15:31:43 ed Exp $
*/

#include "tests.h"
#include <mpi.h>

#define FILE "tst_parallel.nc"
#define NDIMS 2
#define DIMSIZE 24
#define QTR_DATA (DIMSIZE*DIMSIZE/4)
#define NUM_PROC 4

int
main(int argc, char **argv)
{
    /* MPI stuff. */
    int mpi_namelen;		
    char mpi_name[MPI_MAX_PROCESSOR_NAME];
    int mpi_size, mpi_rank;
    MPI_Comm comm = MPI_COMM_WORLD;
    MPI_Info info = MPI_INFO_NULL;

    /* Netcdf-4 stuff. */
    int ncid, v1id, dimids[NDIMS];
    size_t start[NDIMS], count[NDIMS];

    int data[DIMSIZE*DIMSIZE], j, i, res;

    /* Initialize MPI. */
    MPI_Init(&argc,&argv);
    MPI_Comm_size(MPI_COMM_WORLD, &mpi_size);
    MPI_Comm_rank(MPI_COMM_WORLD, &mpi_rank);
    MPI_Get_processor_name(mpi_name, &mpi_namelen);
    /*printf("mpi_name: %s size: %d rank: %d\n", mpi_name, 
      mpi_size, mpi_rank);*/

    if (mpi_rank == 1)
    {
       printf("\n*** tst_parallel testing very basic parallel access.\n");
       printf("*** tst_parallel testing whether we can create file for parallel access and write to it...");
    }

    /* Create a parallel netcdf-4 file. */
    /*nc_set_log_level(3);*/
    if ((res = nc_create_par(FILE, NC_NETCDF4|NC_MPIIO, comm, 
			     info, &ncid))) ERR;

    /* Create two dimensions. */
    if ((res = nc_def_dim(ncid, "d1", DIMSIZE, dimids))) ERR;
    if ((res = nc_def_dim(ncid, "d2", DIMSIZE, &dimids[1]))) ERR;

    /* Create one var. */
    if ((res = nc_def_var(ncid, "v1", NC_INT, NDIMS, dimids, &v1id))) ERR;

    if ((res = nc_enddef(ncid))) ERR;

    /* Set up slab for this process. */
    start[0] = mpi_rank * DIMSIZE/mpi_size;
    start[1] = 0;
    count[0] = DIMSIZE/mpi_size;
    count[1] = DIMSIZE;
    /*printf("mpi_rank=%d start[0]=%d start[1]=%d count[0]=%d count[1]=%d\n",
      mpi_rank, start[0], start[1], count[0], count[1]);*/

    /* Create phoney data. We're going to write a 24x24 array of ints,
       in 4 sets of 144. */
    /*printf("mpi_rank*QTR_DATA=%d (mpi_rank+1)*QTR_DATA-1=%d\n",
      mpi_rank*QTR_DATA, (mpi_rank+1)*QTR_DATA);*/
    for (i=mpi_rank*QTR_DATA; i<(mpi_rank+1)*QTR_DATA; i++)
       data[i] = mpi_rank;

    /*if ((res = nc_var_par_access(ncid, v1id, NC_COLLECTIVE)))
      ERR;*/
    if ((res = nc_var_par_access(ncid, v1id, NC_INDEPENDENT))) ERR;

    /* Write slabs of phoney data. */
    if ((res = nc_put_vara_int(ncid, v1id, start, count, 
			       &data[mpi_rank*QTR_DATA]))) ERR;

    /* Close the netcdf file. */
    if ((res = nc_close(ncid)))	ERR;
    
    /* Shut down MPI. */
    MPI_Finalize();

    if (mpi_rank == 1)
    {
       SUMMARIZE_ERR;
       FINAL_RESULTS;
    }
    return 0;
}
