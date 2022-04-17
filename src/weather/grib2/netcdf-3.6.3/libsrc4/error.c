/*

This file is part of netcdf-4, a netCDF-like interface for HDF5, or a
HDF5 backend for netCDF, depending on your point of view.

This file contains functions relating to logging errors. Also it
contains the functions nc_malloc, nc_calloc, and nc_free.

Copyright 2003, University Corporation for Atmospheric Research. See
netcdf-4/docs/COPYRIGHT file for copying and redistribution
conditions.

$Id: error.c,v 1.5 2005/10/09 13:47:37 ed Exp $
*/

#include <config.h>
#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include "error.h"
#include "assert.h"

/* This contents of this file get skipped if LOGGING is not defined
 * during compile. */
#ifdef LOGGING

/* This keeps track of how many bytes of memory are malloced or
   calloced. */
int nc_allocated_blocks = 0;

extern int nc_log_level;

/* Extra memory debugging can be turned on with the EXTRA_MEM_DEBUG
   flag at compile. */
#ifdef EXTRA_MEM_DEBUG
NC_MEM_DEBUG_T nc_mem_debug[MEM_DEBUG_MAX_BLOCKS];
int nc_mem_blknum = 0;
#endif

/* Substitute malloc to keep track of some stuff.
   Ed Hartnett 11/7/3
*/
void *
nc_malloc(size_t size)
{
   void *ptr;

   nc_allocated_blocks++;
   LOG((6, "nc_malloc called, num_blocks: %d", nc_allocated_blocks));

   /* malloc the memory. */
   ptr = malloc(size);

   /* Extra debugging stuff keeps track of mallocs and frees. */
#ifdef EXTRA_MEM_DEBUG
   if (!ptr)
      LOG((0, "NULL returned from malloc!"));
   if (!size)
      LOG((0, "Malloc called with size = 0!"));
   LOG((6, "%d bytes of memory allocated, at address 0x%x", size, ptr));
   if (nc_mem_blknum > MEM_DEBUG_MAX_BLOCKS)
   {
      LOG((0, "Extra memory debugging ran out of blocks!"));
      return ptr;
   }
   nc_mem_debug[nc_mem_blknum].address = ptr;
   nc_mem_debug[nc_mem_blknum].size = size;
   nc_mem_blknum++;
#endif

   return ptr;
}

/* Phoney calloc for debugging.
   Ed Hartnett 11/7/3
*/
void *
nc_calloc(size_t nmemb, size_t size)
{
   void *ptr;

   nc_allocated_blocks++;
   LOG((6, "nc_calloc called, num_blocks: %d", nc_allocated_blocks));

   ptr = calloc(nmemb, size);

   /* Extra debugging stuff keeps track of mallocs and frees. */
#ifdef EXTRA_MEM_DEBUG
   if (!ptr)
      LOG((0, "NULL returned from calloc!"));
   if (!size)
      LOG((0, "Calloc called with size = 0!"));
   LOG((6, "%d bytes of memory calloced, at address 0x%x", 
	nmemb * size, ptr));
   if (nc_mem_blknum > MEM_DEBUG_MAX_BLOCKS)
   {
      LOG((0, "Extra memory debugging ran out of blocks!"));
      return ptr;
   }
   nc_mem_debug[nc_mem_blknum].address = ptr;
   nc_mem_debug[nc_mem_blknum].size = nmemb * size;
   nc_mem_blknum++;
#endif

   return ptr;
}

/* Phoney free for debugging. */
void
nc_free(void *ptr)
{
   nc_allocated_blocks--;
   LOG((6, "nc_free called, num_blocks: %d", nc_allocated_blocks));

   /* Extra debugging stuff keeps track of mallocs and frees. */
#ifdef EXTRA_MEM_DEBUG
   if (!ptr)
      LOG((0, "free called on NULL!"));
   {
      int i;
      for (i=0; i<MEM_DEBUG_MAX_BLOCKS; i++)
	 if (nc_mem_debug[i].address == ptr)
	 {
	    if (!nc_mem_debug[i].size)
	       LOG((0, "Free called, but size alread zero!"));
	    LOG((6, "Freeing memory at 0x%x", ptr));
	    nc_mem_debug[i].address = NULL;
	    nc_mem_debug[i].size = 0;
	    break;
	 }
      if (i==MEM_DEBUG_MAX_BLOCKS)
	 LOG((0, "Couldn't find address 0x%x in nc_mem_debug array!", ptr));
   }
#endif /* EXTRA_MEM_DEBUG */

   free(ptr);
   return;
}

/* This function prints out a message, if the severity of the message
   is lower than the global nc_log_level. To use it, do something like
   this:
   
   nc_log(0, "this computer will explode in %d seconds", i);

   After the first arg (the severity), use the rest like a normal
   printf statement. Output will appear on stdout.

   This function is heavily based on the function in section 15.5 of
   the C FAQ. */
void nc_log(int severity, const char *fmt, ...)
{
   va_list argp;
   int t;

   /* If the severity is greater than the log level, we don' care to
      print this message. */
   if (severity > nc_log_level)
      return;

   /* If the severity is zero, this is an error. Otherwise insert that
      many tabs before the message. */
   if (!severity)
      fprintf(stdout, "ERROR: ");
   for (t=0; t<severity; t++)
      fprintf(stdout, "\t");

   /* Print out the variable list of args with vprintf. */
   va_start(argp, fmt);
   vfprintf(stdout, fmt, argp);
   va_end(argp);
   
   /* Put on a final linefeed. */
   fprintf(stdout, "\n");
   fflush(stdout);
}

/* For debugging purposes, check memory stuff to make sure everything
   that was malloced was freed. This function only exists if the LOGGING
   option is used at compile. */
void
nc_exit()
{
   /* Check memory stuff. */
   if (nc_allocated_blocks)
      LOG((0, "Oh oh, %d allocated blocks unaccounted for at nc_exit!",
	   nc_allocated_blocks));

   /* "No one gets left behind!" - Billy Blazes, Rescue Hero */
#ifdef EXTRA_MEM_DEBUG
   {
      int i;
      for (i=0; i<MEM_DEBUG_MAX_BLOCKS; i++)
      {
	 if (nc_mem_debug[i].address || nc_mem_debug[i].size)
	    LOG((0, "Non-NULL address pointer(0x%x) or size(%d) in nc_mem_debug "
		 "at library exit!", nc_mem_debug[i].address, nc_mem_debug[i].size));
      }
   }
#endif /* EXTRA_MEM_DEBUG */
}

#endif /* ifdef LOGGING */

