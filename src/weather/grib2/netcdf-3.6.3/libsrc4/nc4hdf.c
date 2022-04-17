/*
  This file is part of netcdf-4, a netCDF-like interface for HDF5, or a
  HDF5 backend for netCDF, depending on your point of view.

  This file contains functions internal to the netcdf4 library. None of
  the functions in this file are exposed in the exetnal API. These
  functions handle the HDF interface.

  Copyright 2003-2008, University Corporation for Atmospheric
  Research. See the COPYRIGHT file for copying and redistribution
  conditions.

  $Id: nc4hdf.c,v 1.149 2008/06/10 15:38:34 ed Exp $
*/

#include <nc4internal.h>
#include <H5DSpublic.h>

extern NC_FILE_INFO_T *nc_file;

hid_t global_hdf_string_typeid = 0;

#define DIM_WITHOUT_VARIABLE "This is a netCDF dimension but not a netCDF variable."

/* These are the special attributes added by the HDF5 dimension scale
 * API. They will be ignored by netCDF-4. */
#define REFERENCE_LIST "REFERENCE_LIST"
#define CLASS "CLASS"
#define DIMENSION_LIST "DIMENSION_LIST"
#define NAME "NAME"

#define MIN_DEFLATE_LEVEL 0
#define MAX_DEFLATE_LEVEL 9

/* This function is needed to handle one special case: what if the
 * user defines a dim, writes metadata, then goes back into define
 * mode and adds a coordinate var for the already existing dim. In
 * that case, I need to recreate the dim's dimension scale dataset,
 * and then I need to go to every var in the file which uses that
 * dimension, and attach the new dimension scale. */
static int
rec_reattach_scales(NC_GRP_INFO_T *grp, int dimid, hid_t dimscaleid)
{
   NC_VAR_INFO_T *var;
   NC_GRP_INFO_T *child_grp;
   int d;
   int retval;

   assert(grp && grp->name && dimid >= 0 && dimscaleid >= 0);
   LOG((3, "rec_reattach_scales: grp->name %s", grp->name));

   /* If there are any child groups, attach dimscale there, if needed. */
   for (child_grp = grp->children; child_grp; child_grp = child_grp->next)
      if ((retval = rec_reattach_scales(child_grp, dimid, dimscaleid)))
	 return retval;

   /* Find any vars that use this dimension id. */
   for (var = grp->var; var; var = var->next)
      for (d = 0; d < var->ndims; d++)
	 if (var->dimids[d] == dimid && !var->dimscale)
	 {
	    LOG((2, "rec_reattach_scaled: attaching scale for dimid %d to var %s", 
		 var->dimids[d], var->name));
	    if (var->created)
	    {
	       if (H5DSattach_scale(var->hdf_datasetid, dimscaleid, d) < 0)
		  return NC_EHDFERR;
	       var->dimscale_attached[d]++;
	    }
	 }

   return NC_NOERR;
}

/* This function is needed to handle one special case: what if the
 * user defines a dim, writes metadata, then goes back into define
 * mode and adds a coordinate var for the already existing dim. In
 * that case, I need to recreate the dim's dimension scale dataset,
 * and then I need to go to every var in the file which uses that
 * dimension, and attach the new dimension scale. */
static int
rec_detach_scales(NC_GRP_INFO_T *grp, int dimid, hid_t dimscaleid)
{
   NC_VAR_INFO_T *var;
   NC_GRP_INFO_T *child_grp;
   int d;
   int retval;

   assert(grp && grp->name && dimid >= 0 && dimscaleid >= 0);
   LOG((3, "rec_detach_scales: grp->name %s", grp->name));

   /* If there are any child groups, attach dimscale there, if needed. */
   for (child_grp = grp->children; child_grp; child_grp = child_grp->next)
      if ((retval = rec_reattach_scales(child_grp, dimid, dimscaleid)))
	 return retval;

   /* Find any (already created) vars that use this dimension id. */
   for (var = grp->var; var; var = var->next)
      for (d = 0; d < var->ndims; d++)
	 if (var->dimids[d] == dimid && !var->dimscale)
	 {
	    LOG((2, "rec_detach_scales: detaching scale for dimid %d to var %s", 
		 var->dimids[d], var->name));
	    if (var->created)
	    {
	       if (H5DSdetach_scale(var->hdf_datasetid, dimscaleid, d) < 0)
		  return NC_EHDFERR;
	       var->dimscale_attached[d] = 0;
	    }
	 }

   return NC_NOERR;
}

/* This function is called when reading a file's metadata for each
 * dimension scale attached to a variable.*/
static herr_t 
dimscale_visitor(hid_t did, unsigned dim, hid_t dsid, 
		 void *dimscale_hdf5_objids)
{
   H5G_stat_t statbuf;

   /* Get more info on the dimscale object.*/
   if (H5Gget_objinfo(dsid, ".", 1, &statbuf) < 0)
      return -1;

   /* Pass this information back to caller. */
/*   (*(HDF5_OBJID_T *)dimscale_hdf5_objids).fileno = statbuf.fileno;
     (*(HDF5_OBJID_T *)dimscale_hdf5_objids).objno = statbuf.objno;*/
   (*(HDF5_OBJID_T *)dimscale_hdf5_objids).fileno[0] = statbuf.fileno[0];
   (*(HDF5_OBJID_T *)dimscale_hdf5_objids).fileno[1] = statbuf.fileno[1];
   (*(HDF5_OBJID_T *)dimscale_hdf5_objids).objno[0] = statbuf.objno[0];
   (*(HDF5_OBJID_T *)dimscale_hdf5_objids).objno[1] = statbuf.objno[1];
   return 0;
}

/* Open the dataset and leave it open. */
int 
nc4_open_var_grp(NC_GRP_INFO_T *grp, int varid, hid_t *dataset)
{
   NC_VAR_INFO_T *var;
   
   /* Find the requested varid. */
   for (var = grp->var; var; var = var->next)
      if (var->varid == varid)
	 break;
   if (!var)
      return NC_ENOTVAR;
   
   /* Open this databset. */
   if ((*dataset = H5Dopen(grp->hdf_grpid, var->name)) < 0)
      return NC_ENOTVAR;
   
   return NC_NOERR;
}

/* Write or read one element of data. */
int
nc4_pg_var1(NC_PG_T pg, NC_FILE_INFO_T *nc, int ncid, int varid, 
	    const size_t *indexp, nc_type xtype, int is_long, void *ip)
{
   NC_GRP_INFO_T *grp;
   NC_VAR_INFO_T *var;
   int i;
   size_t start[NC_MAX_DIMS], count[NC_MAX_DIMS];
   int retval;

   /* Find file and var, cause I need the number of dims. */
   assert(nc);
   if ((retval = nc4_find_g_var_nc(nc, ncid, varid, &grp, &var)))
      return retval;
   assert(grp && var && var->name);

   /* Set up the count and start arrays. */
   for (i=0; i<var->ndims; i++)
   {
      start[i] = indexp[i];
      count[i] = 1;
   }

   return nc4_pg_vara(pg, nc, ncid, varid, start, count, xtype, 
		  is_long, ip);
}

/* Get the default fill value for an atomic type. Memory for
 * fill_value must already be allocated, or you are DOOMED!!!*/
int
nc4_get_default_fill_value(nc_type xtype, void *fill_value)
{
   switch (xtype)
   {
      case NC_BYTE:
	 *(signed char *)fill_value = NC_FILL_BYTE;
	 break;
      case NC_CHAR:
	 *(char *)fill_value = NC_FILL_CHAR;
	 break;
      case NC_SHORT:
	 *(short *)fill_value = NC_FILL_SHORT;
	 break;
      case NC_INT:
	 *(int *)fill_value = NC_FILL_INT;
	 break;
      case NC_FLOAT:
	 *(float *)fill_value = NC_FILL_FLOAT;
	 break;
      case NC_DOUBLE:
	 *(double *)fill_value = NC_FILL_DOUBLE;
	 break;
      case NC_UBYTE:
	 *(unsigned char *)fill_value = NC_FILL_UBYTE;
	 break;
      case NC_USHORT:
	 *(unsigned short *)fill_value = NC_FILL_USHORT;
	 break;
      case NC_UINT:
	 *(unsigned int *)fill_value = NC_FILL_UINT;
	 break;
      case NC_INT64:
	 *(long long *)fill_value = NC_FILL_INT64;
	 break;
      case NC_UINT64:
	 *(unsigned long long *)fill_value = NC_FILL_UINT64;
	 break;
      case NC_STRING:
	 strcpy((char *)fill_value, "");
	 break;
      default:
	 return NC_EINVAL;
   }

   return NC_NOERR;
}

/* What fill value should be sued for a variable? */
static int
get_fill_value(NC_HDF5_FILE_INFO_T *h5, NC_VAR_INFO_T *var, void **fillp)
{   
   size_t size;
   int retval;

   /* Find out how much space we need for this type's fill value. */
   if ((retval = nc4_get_typelen_mem(h5, var->xtype, 0, &size)))
      return retval;

   /* Strings have a size of one for the empty sting (to hold the
    * null), otherwise the length of the users fill_value string, plus
    * one. */
   if (var->xtype == NC_STRING)
   {
      if (var->fill_value)
	 size = strlen((char *)var->fill_value) + 1;
      else
	 size = 1;
   }
   
   /* Allocate the space. VLENS are different, of course. */
   if (var->class == NC_VLEN)
   {
      if (!((*fillp) = nc_malloc(sizeof(nc_vlen_t))))
	 return NC_ENOMEM;
   }
   else
   {
      if (!((*fillp) = nc_malloc(size)))
	 return NC_ENOMEM;
   }

   /* If the user has set a fill_value for this var, use, otherwise
    * find the default fill value. */
   if (var->fill_value)
   {
      LOG((4, "Found a fill value for var %s", var->name));
      if (var->class == NC_VLEN)   
      {
	 nc_vlen_t *in_vlen = (nc_vlen_t *)(var->fill_value), *fv_vlen = (nc_vlen_t *)(*fillp);
	 fv_vlen->len = in_vlen->len;
	 if (!(fv_vlen->p = malloc(size * in_vlen->len)))
	    return NC_ENOMEM;
	 memcpy(fv_vlen->p, in_vlen->p, in_vlen->len * size);
      }
      else
	 memcpy((*fillp), var->fill_value, size);
   }
   else
   {
      if ((nc4_get_default_fill_value(var->xtype, *fillp)))
      {
	 nc_free(*fillp);
	 *fillp = NULL;
      }
   }

   return NC_NOERR;
}

/* Given a netcdf type, return appropriate HDF typeid. */
static int
get_hdf_typeid(NC_HDF5_FILE_INFO_T *h5, nc_type xtype, 
	       hid_t *hdf_typeid, int endianness)
{
   NC_TYPE_INFO_T *type;
   hid_t typeid = 0;
   int retval = NC_NOERR;

   assert(hdf_typeid && h5);

   *hdf_typeid = -1;
   switch (xtype)
   {
      case NC_NAT: /* NAT = 'Not A Type' (c.f. NaN) */
	 return NC_EBADTYPE;
      case NC_BYTE: /* signed 1 byte integer */
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_I8LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_I8BE;
	 else
	    *hdf_typeid = H5T_NATIVE_SCHAR;
	 break;
      case NC_CHAR: /* ISO/ASCII character */
	 typeid = H5Tcopy(H5T_C_S1);
	 if (H5Tset_strpad(typeid, H5T_STR_NULLTERM) < 0)
	    BAIL(NC_EVARMETA);
	 *hdf_typeid = typeid;
	 break;
      case NC_SHORT: /* signed 2 byte integer */
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_I16LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_I16BE;
	 else
	    *hdf_typeid = H5T_NATIVE_SHORT;
	 break;
      case NC_INT: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_I32LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_I32BE;
	 else
	    *hdf_typeid = H5T_NATIVE_INT;
	 break;
      case NC_FLOAT: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_IEEE_F32LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_IEEE_F32BE;
	 else
	    *hdf_typeid = H5T_NATIVE_FLOAT;
	 break;
      case NC_DOUBLE:
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_IEEE_F64LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_IEEE_F64BE;
	 else
	    *hdf_typeid = H5T_NATIVE_DOUBLE;
	 break;
      case NC_UBYTE: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_U8LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_U8BE;
	 else
	    *hdf_typeid = H5T_NATIVE_UCHAR;
	 break;
      case NC_USHORT:
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_U16LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_U16BE;
	 else
	    *hdf_typeid = H5T_NATIVE_USHORT;
	 break;
      case NC_UINT: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_U32LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_U32BE;
	 else
	    *hdf_typeid = H5T_NATIVE_UINT;
	 break;
      case NC_INT64: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_I64LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_I64BE;
	 else
	    *hdf_typeid = H5T_NATIVE_LLONG;
	 break;
      case NC_UINT64: 
	 if (endianness == NC_ENDIAN_LITTLE)
	    *hdf_typeid = H5T_STD_U64LE;
	 else if (endianness == NC_ENDIAN_BIG)
	    *hdf_typeid = H5T_STD_U64BE;
	 else
	    *hdf_typeid = H5T_NATIVE_ULLONG;
	 break;
      case NC_STRING: 
#ifndef USE_PARALLEL
	 if (!global_hdf_string_typeid)
	 {
#endif /* USE_PARALLEL */
	    if ((global_hdf_string_typeid =  H5Tcopy(H5T_C_S1)) < 0) 
	       return NC_EHDFERR;
	    if (H5Tset_size(global_hdf_string_typeid, H5T_VARIABLE) < 0)
	       return NC_EHDFERR;
#ifndef USE_PARALLEL
	 }
#endif /* USE_PARALLEL */
	 *hdf_typeid = global_hdf_string_typeid;
	 break;
      default:
	 /* Maybe this is a user defined type? */
	 if (!(retval = nc4_find_type(h5, xtype, &type)))
	 {
	    if (!type)
	       return NC_EBADTYPE;
	    *hdf_typeid = type->hdf_typeid;
	 }
   }

   if (*hdf_typeid == -1)
      return NC_EBADTYPE;
   
   return NC_NOERR;

  exit:
   if (xtype == NC_CHAR && typeid > 0 && H5Tclose(typeid) < 0)
      BAIL2(NC_EHDFERR);      
   return retval;
}

/* Write or read some data, an arrayfull at a time. 

   Oh, better far to live and die
   Under the brave black flag I fly,
   Than play a sanctimonious part,
   With a pirate head and a pirate heart.

   Away to the cheating world go you,
   Where pirates all are well-to-do.
   But I'll be true to the song I sing,
   And live and die a Pirate king.

*/
int 
nc4_pg_vara(NC_PG_T pg, NC_FILE_INFO_T *nc, int ncid, int varid, 
	const size_t *startp, const size_t *countp, 
	nc_type mem_nc_type, int is_long, void *data)
{
   NC_GRP_INFO_T *grp;
   NC_HDF5_FILE_INFO_T *h5;
   NC_VAR_INFO_T *var;
   NC_DIM_INFO_T *dim;

   hid_t datasetid = 0, file_spaceid = 0, mem_spaceid = 0;
   hid_t mem_typeid = 0, xfer_plistid;
   size_t file_type_size;

   hsize_t *xtend_size = NULL, count[NC_MAX_DIMS];
   hsize_t fdims[NC_MAX_DIMS], fmaxdims[NC_MAX_DIMS];
   hsize_t start[NC_MAX_DIMS];
   void *fillvalue = NULL;
   int need_to_extend = 0, fill_value_recs = 0;
   int scalar = 0, retval = NC_NOERR, range_error = 0, i, d2;
   void *bufr = NULL;
#ifndef HDF5_CONVERT   
   int need_to_convert = 0;
   size_t len = 1;
#endif

   /* Find our metadata for this file, group, and var. */
   assert(nc);
   if ((retval = nc4_find_g_var_nc(nc, ncid, varid, &grp, &var)))
      return retval;
   h5 = nc->nc4_info;
   assert(grp && h5 && var && var->name);

   LOG((3, "nc4_pg_vara: pg %d var->name %s mem_nc_type %d is_long %d", 
	pg, var->name, mem_nc_type, is_long));

   /* If mem_nc_type is NC_NAT, it means we want to use the file type
    * as the mem type as well. */
   if (mem_nc_type == NC_NAT)
      mem_nc_type = var->xtype;
   assert(mem_nc_type);

   /* No NC_CHAR conversions, you pervert! */
   if (var->xtype != mem_nc_type && 
       (var->xtype == NC_CHAR || mem_nc_type == NC_CHAR))
      return NC_ECHAR;

   /* Trying to write to a read-only file? No way, Jose! */
   if (pg == PUT && h5->no_write)
      return NC_EPERM;
   
   /* If we're in define mode, we can't read or write data. */
   if (h5->flags & NC_INDEF)
   {
      if (h5->cmode & NC_CLASSIC_MODEL)
	 return NC_EINDEFINE;
      if ((retval = nc4_enddef_netcdf4_file(h5)))
	 return retval;
   }

   /* Convert from size_t and ptrdiff_t to hssize_t, and hsize_t. */
   for (i=0; i<var->ndims; i++)
   {
      start[i] = startp[i];
      count[i] = countp[i];
   }
   LOG((4, "nc4_pg_vara: var name %s ndims %d", var->name, var->ndims)); 
   
   /* Open this var's dataset. */
   if ((retval = nc4_open_var_grp(grp, varid, &datasetid))) 
      BAIL(retval);

   /* Get file space of data. */
   if ((file_spaceid = H5Dget_space(datasetid)) < 0) 
      BAIL(NC_EHDFERR);

   /* Check to ensure the user selection is
    * valid. H5Sget_simple_extent_dims gets the sizes of all the dims
    * and put them in fdims. */
   if (H5Sget_simple_extent_dims(file_spaceid, fdims, fmaxdims) > 0)
   {
#ifdef LOGGING
      /* Print some debugging info... */
      LOG((4, "File space, and requested:"));
      for (d2=0; d2<var->ndims; d2++)
      {
	 LOG((4, "fdims[%d]=%d fmaxdims[%d]=%d", d2, fdims[d2], d2, 
	      fmaxdims[d2]));
	 LOG((4, "start[%d]=%d  count[%d]=%d", d2, (int)start[d2], 
	      d2, (int)count[d2]));
      }
#endif
      /* Unlimited dimnsions are exempted from this tax, if this is a PUT! */
      for (d2=0; d2<var->ndims; d2++)
      {
	 for (dim=grp->dim; dim; dim=dim->next)
	 {
	    if (dim->dimid == var->dimids[d2])
	    {
	       if (!dim->unlimited)
	       {
		  if (start[d2] >= (hssize_t)fdims[d2])
		     BAIL_QUIET(NC_EINVALCOORDS);
		  if (start[d2] + count[d2] > fdims[d2])
		     BAIL_QUIET(NC_EEDGE);
	       }
	       if (dim->unlimited && pg == GET)
	       {
		  size_t ulen;
		  /* We can't go beyond the latgest current extent of
		     the unlimited dim. */
		  if ((retval = nc_inq_dimlen(ncid, dim->dimid, &ulen)))
		     BAIL(retval);
		  
		  /* Check for out of bound requests. */
		  if (start[d2] >= (hssize_t)ulen)
		     BAIL_QUIET(NC_EINVALCOORDS);
		  if (start[d2] + count[d2] > ulen)
		     BAIL_QUIET(NC_EEDGE);

		  /* THings get a little tricky here. If we're getting
		     a GET request beyond the end of this var's
		     current length in an unlimited dimension, we'll
		     later need to return the fill value for the
		     variable. */
		  if (start[d2] >= (hssize_t)fdims[d2])
		     fill_value_recs = count[d2];
		  else if (start[d2]+count[d2] > fdims[d2])
		     fill_value_recs = count[d2] - (fdims[d2] - start[d2]);
		  count[d2] -= fill_value_recs;
	       }
	    }
	 }
      }
   }

   /* A little quirk: if any of the count values are zero, then
      return success and forget about it. */
   for (d2=0; d2<var->ndims; d2++)
      if (count[d2] == 0)
	 goto exit;
   
   /* Now you would think that no one would be crazy enough to write
      a scalar dataspace with one of the array function calls, but you
      would be wrong. So let's check to see if the dataset is
      scalar. If it is, we won't try to set up a hyperslab. */
   if (H5Sget_simple_extent_type(file_spaceid) == H5S_SCALAR)
   {
      if ((mem_spaceid = H5Screate(H5S_SCALAR)) < 0) 
	 BAIL(NC_EHDFERR);
      scalar++;
   }
   else
   {
      if (H5Sselect_hyperslab(file_spaceid, H5S_SELECT_SET, 
			      start, NULL, count, NULL) < 0)
	 BAIL(NC_EHDFERR);
      /* Create a space for the memory, just big enough to hold the slab
	 we want. */
      if ((mem_spaceid = H5Screate_simple(var->ndims, count, NULL)) < 0) 
	 BAIL(NC_EHDFERR);
   }
   
   /* Later on, we will need to know the size of this type in the
    * file. */
   if ((retval = nc4_get_typelen_mem(h5, var->xtype, 0, &file_type_size)))
      return retval;

#ifndef HDF5_CONVERT   
   /* Are we going to convert any data? (No converting of compound or
    * opaque types.) */
   if ((mem_nc_type != var->xtype || (var->xtype == NC_INT && is_long)) && 
       mem_nc_type != NC_COMPOUND && mem_nc_type != NC_OPAQUE)
   {
      /* We must convert - allocate a buffer. */
      need_to_convert++;
      if (var->ndims)
	 for (d2=0; d2<var->ndims; d2++)
	    len *= countp[d2];
      LOG((4, "converting data for var %s type=%d len=%d", var->name, 
	   var->xtype, len));

      /* If we're reading, we need bufr to have enough memory to store
       * the data in the file. If we're writing, we need bufr to be
       * big enough to hold all the data in the file's type. */
      if (!(bufr = nc_malloc(len * file_type_size)))
	 BAIL(NC_ENOMEM);
   }
   else
#endif /* ifndef HDF5_CONVERT */
      bufr = data;

#ifdef HDF5_CONVERT
   /* Get the HDF type of the data in memory. */
   if ((retval = get_hdf_typeid(h5, mem_nc_type, &mem_typeid, var->endianness)))
      BAIL(retval);
#else
   /* Get the HDF type of the data in memory. (If we're writing data,
      we may have to change the mem_typeid later.) */
   if ((retval = get_hdf_typeid(h5, var->xtype, &mem_typeid, var->endianness)))
      BAIL(retval);
#endif
   
   /* Create the data transfer property list. */
   if ((xfer_plistid = H5Pcreate(H5P_DATASET_XFER)) < 0)
      BAIL(NC_EPARINIT);
/*   if (H5Pset_cache(xfer_plistid, 1000, 1000, 256000000, 0.75) < 0)
     BAIL(NC_EPARINIT);*/

   /* Apply the callback function which will detect range
    * errors. Which one to call depends on the length of the
    * destination buffer type. */
#ifdef HDF5_CONVERT
   if (H5Pset_type_conv_cb(xfer_plistid, except_func, 
			   &range_error) < 0) 
      BAIL(NC_EHDFERR);
#endif

#ifdef USE_PARALLEL
   /* If netcdf is configured with --enable-parallel, then parallel
    * access can be used, and, if this file was opened or created
    * for parallel access, we need to set the transfer mode. */
   if (h5->parallel)
   {
      int hdf5_xfer_mode = (var->parallel_access != NC_INDEPENDENT) ?
	 H5FD_MPIO_COLLECTIVE : H5FD_MPIO_INDEPENDENT;
      if (H5Pset_dxpl_mpio(xfer_plistid, hdf5_xfer_mode) < 0)
	 BAIL(NC_EPARINIT);
      LOG((4, "hdf5_xfer_mode: %d H5FD_MPIO_COLLECTIVE: %d H5FD_MPIO_INDEPENDENT: %d", 
	   hdf5_xfer_mode, H5FD_MPIO_COLLECTIVE, H5FD_MPIO_INDEPENDENT));
   }
#endif

   /* Read/write this hyperslab into memory. */
   if (pg == GET)
   {
      hid_t native_typeid;
      LOG((5, "About to H5Dread some data..."));
      if ((native_typeid = H5Tget_native_type(mem_typeid, H5T_DIR_DEFAULT)) < 0)
	 BAIL(NC_EHDFERR);
      if (H5Dread(datasetid, native_typeid, mem_spaceid, file_spaceid, xfer_plistid, bufr) < 0)
	 BAIL(NC_EHDFERR);
/*       if (H5Dread(datasetid, mem_typeid, mem_spaceid, file_spaceid, xfer_plistid, bufr) < 0) */
/* 	 BAIL(NC_EHDFERR); */

#ifndef HDF5_CONVERT
      /* Eventually the block below will go away. Right now it's
	 needed to support conversions between int/float, and range
	 checking converted data in the netcdf way. These features are
	 being added to HDF5 at the HDF5 World Hall of Coding right
	 now, by a staff of thousands of programming gnomes. */
      if (need_to_convert)
      {
	 if ((retval = nc4_convert_type(bufr, data, var->xtype, mem_nc_type, 
				    len, &range_error, var->fill_value, 
				    (h5->cmode & NC_CLASSIC_MODEL), 0, is_long)))
	    BAIL(retval);

	 /* For strict netcdf-3 rules, ignore erange errors between UBYTE
	  * and BYTE types. */
	 if ((h5->cmode & NC_CLASSIC_MODEL) &&
	     (var->xtype == NC_UBYTE || var->xtype == NC_BYTE) &&
	     (mem_nc_type == NC_UBYTE || mem_nc_type == NC_BYTE) &&
	     range_error)
	    range_error = 0;
      }
#endif

      /* Now we need to fake up any further data that was asked for,
	 using the fill values instead. First skip past the data we
	 just read, if any. */
      if (!scalar)
      {
/* 	 void *filldata; */
/* 	 int real_data_size = 0, fake_data_size = 0; */
/* 	 hid_t clistid = 0; */

	 /* Get the fill value from the HDF5 variable. */
/*	 if (!(fillvalue = nc_malloc(type_size)))
	 BAIL(NC_ENOMEM);
	 if ((clistid = H5Dget_create_plist(datasetid)) < 0)
	 BAIL(NC_EHDFERR);
	 if (H5Pget_fill_value(clistid, var->xtype, fillvalue) < 0)
	 BAIL(NC_EHDFERR);*/

	 /* Copy the fill value into the rest of the data buffer. */
/*	 filldata = (char *)data + real_data_size;
	 for (i=0; i<fake_data_size; i++)
	 {
	 memcpy(filldata, fillvalue, type_size);
	 filldata = (char *)filldata + 1;
	 ((char *)filldata)++;
	 }*/
      }
   }
   else /* it's a PUT - we're writing data. */
   {
      /* Does the dataset have to be extended? If it's already
	 extended to the required size, it will do no harm to reextend
	 it to that size. */
      if (var->ndims)
      {
	 if (!(xtend_size = nc_malloc(var->ndims * sizeof(hsize_t))))
	    BAIL(NC_ENOMEM);
	 for (d2=0; d2<var->ndims; d2++)
	 {
	    if ((retval = nc4_find_dim(grp, var->dimids[d2], &dim)))
	       BAIL(retval);
	    if (dim->unlimited)
	    {
	       if (start[d2] + count[d2] > fdims[d2])
	       {
		  need_to_extend++;
		  xtend_size[d2] = start[d2] + count[d2];
	       }
	       if (start[d2] + count[d2] > dim->len)
	       {
		  dim->len = start[d2] + count[d2];
		  dim->extended++;
	       }
	    }
	    else
	    {
	       xtend_size[d2] = dim->len;
	    }
	 }

	 /* If we need to extend it, we also need a new file_spaceid
	    to reflect the new size of the space. */
	 if (need_to_extend)
	 {
	    LOG((4, "extending dataset"));
	    if (H5Dextend(datasetid, xtend_size) < 0)
	       BAIL(NC_EHDFERR);
	    if ((file_spaceid = H5Dget_space(datasetid)) < 0) 
	       BAIL(NC_EHDFERR);
	    if (H5Sselect_hyperslab(file_spaceid, H5S_SELECT_SET, 
				    start, NULL, count, NULL) < 0)
	       BAIL(NC_EHDFERR);
	 }
      }

#ifndef HDF5_CONVERT
      /* Do we need to convert the data? */
      if (need_to_convert)
      {
	 if ((retval = nc4_convert_type(data, bufr, mem_nc_type, var->xtype, 
				    len, &range_error, var->fill_value,
				    (h5->cmode & NC_CLASSIC_MODEL), is_long, 0)))
	    BAIL(retval);
      }
#endif

      /* Write the data. At last! */
      LOG((4, "about to H5Dwrite datasetid 0x%x mem_typeid 0x%x mem_spaceid"
	   " 0x%x file_spaceid 0x%x", datasetid, mem_typeid, mem_spaceid, 
	   file_spaceid));
      {
	 hid_t native_typeid;
	 if ((native_typeid = H5Tget_native_type(mem_typeid, H5T_DIR_DEFAULT)) < 0)
	    BAIL(NC_EHDFERR);
	 if (H5Dwrite(datasetid, native_typeid, mem_spaceid, file_spaceid, 
		      xfer_plistid, bufr) < 0)
	    BAIL(NC_EHDFERR);
	 LOG((4, "data written"));
      }

      /* Remember that we have written to this var so that Fill Value
       * can't be set for it. */
      if (!var->written_to)
	 var->written_to++;
   } /* it's a PUT */

   /* For strict netcdf-3 rules, ignore erange errors between UBYTE
    * and BYTE types. */
   if ((h5->cmode & NC_CLASSIC_MODEL) &&
       (var->xtype == NC_UBYTE || var->xtype == NC_BYTE) &&
       (mem_nc_type == NC_UBYTE || mem_nc_type == NC_BYTE) &&
       range_error)
      range_error = 0;

  exit:
   if (datasetid > 0 && H5Dclose(datasetid) < 0)
      BAIL2(NC_EHDFERR);
   if (var->xtype == NC_CHAR && mem_typeid > 0 && H5Tclose(mem_typeid) < 0)
      BAIL2(NC_EHDFERR);
   if (file_spaceid > 0 && H5Sclose(file_spaceid) < 0)
      BAIL2(NC_EHDFERR);
   if (mem_spaceid > 0 && H5Sclose(mem_spaceid) < 0)
      BAIL2(NC_EHDFERR);
#ifdef USE_PARALLEL
   if (h5->parallel && (H5Pclose(xfer_plistid) < 0))
      BAIL2(NC_EPARINIT);
#endif
#ifndef HDF5_CONVERT
   if (need_to_convert) nc_free(bufr);
#endif
   if (xtend_size) nc_free(xtend_size);
   if (fillvalue) nc_free(fillvalue);

   /* If there was an error return it, otherwise return any potential
      range error value. If none, return NC_NOERR as usual.*/
   if (retval)      
      return retval;
   if (range_error)
      return NC_ERANGE;
   return NC_NOERR;
}

/* Given an HDF5 type, set a pointer to netcdf type. */
static int
get_netcdf_type(NC_HDF5_FILE_INFO_T *h5, hid_t hdf_type1, nc_type *xtype)
{
   NC_TYPE_INFO_T *type;
   hid_t class, native_typeid;
   htri_t is_str, equal;

   assert(h5 && xtype);

   if ((class = H5Tget_class(hdf_type1)) < 0)
      return NC_EHDFERR;

   /* H5Tequal doesn't work with H5T_C_S1 for some reason. But
    * H5Tget_class will return H5T_STRING if this is a string. */
   if (class == H5T_STRING)
   {
      if ((is_str = H5Tis_variable_str(hdf_type1)) < 0)
	 return NC_EHDFERR;
      if (is_str)
	 *xtype = NC_STRING;
      else
	 *xtype = NC_CHAR;
      return NC_NOERR;
   }
   else if (class == H5T_INTEGER || class == H5T_FLOAT)
   {
      /* For integers and floats, we have to worry about endianness. */
      if ((native_typeid = H5Tget_native_type(hdf_type1, H5T_DIR_ASCEND)) < 0)
	 return NC_EHDFERR;

      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_SCHAR)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_BYTE;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_SHORT)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_SHORT;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_INT)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_INT;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_FLOAT)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_FLOAT;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_DOUBLE)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_DOUBLE;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_UCHAR)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_UBYTE;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_USHORT)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_USHORT;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_UINT)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_UINT;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_LLONG)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_INT64;
	 return NC_NOERR;
      }
      if ((equal = H5Tequal(native_typeid, H5T_NATIVE_ULLONG)) < 0)
	 return NC_EHDFERR;
      if (equal)
      {
	 *xtype = NC_UINT64;
	 return NC_NOERR;
      }
   }

   /* Maybe we already know about this type. */
   if((type = nc4_rec_find_hdf_type(h5->root_grp, hdf_type1)))
   {
      *xtype = type->nc_typeid;
      return NC_NOERR;
   }
   
   *xtype = NC_NAT;
   return NC_NOERR;
}

/* This function creates the HDF5 dataset for a variabale. */
static int
var_create_dataset(NC_GRP_INFO_T *grp, NC_VAR_INFO_T *var)
{
   NC_GRP_INFO_T *g;
   hid_t plistid=0, typeid=0, spaceid=0, dsid=0;
   hsize_t *chunksize = NULL, *dimsize = NULL, *maxdimsize = NULL;
   size_t type_len;
   int d;
   NC_DIM_INFO_T *dim = NULL;
   void *fillp = NULL;
   int dims_found = 0;
   int set_chunksizes = 0;
   int retval = NC_NOERR;
   
   LOG((3, "var_create_dataset: name %s", var->name));

   /* Scalar or not, we need a creation property list. */
   if ((plistid = H5Pcreate(H5P_DATASET_CREATE)) < 0)
      BAIL(NC_EHDFERR);

   /* Find the HDF5 type of the dataset. */
   if ((retval = get_hdf_typeid(grp->file->nc4_info, var->xtype, 
				&typeid, var->endianness)))
      BAIL(retval);

   /* Figure out what fill value to set, if any. */
   if (!var->no_fill)
   {
      if ((retval = get_fill_value(grp->file->nc4_info, var, &fillp)))
	 BAIL(retval);

      /* If there is a fill value, set it. */
      if (fillp)
      {
	 if (var->xtype == NC_STRING)
	 {
	    if (H5Pset_fill_value(plistid, typeid, &fillp) < 0)
	       BAIL(NC_EHDFERR);
	 }
	 else 
	 {
	    if (H5Pset_fill_value(plistid, typeid, fillp) < 0)
	       BAIL(NC_EHDFERR);
	    if (var->class == NC_VLEN)
	       nc_free_vlen((nc_vlen_t *)fillp);
	 }
      }
   }

   /* If the user wants to shuffle the data, set that up now. */
   if (var->shuffle)
      if (H5Pset_shuffle(plistid) < 0)
	 BAIL(NC_EHDFERR);

   /* If the user wants to deflate the data, set that up now. */
   if (var->deflate)
      if (H5Pset_deflate(plistid, var->deflate_level) < 0)
	 BAIL(NC_EHDFERR);
  
   /* If the user wants to fletcher error correcton, set that up now. */
   if (var->fletcher32)
      if (H5Pset_fletcher32(plistid) < 0)
	 BAIL(NC_EHDFERR);

   /* If ndims non-zero, get info for all dimensions. We look up the
      dimids and get the len of each dimension. We need this to create
      the space for the dataset. In netCDF a dimension length of zero
      means an unlimited dimension. */
   if (var->ndims)
   {
      if (!(dimsize = nc_malloc(var->ndims * sizeof(hsize_t))))
	 BAIL(NC_ENOMEM);
      if (!(maxdimsize = nc_malloc(var->ndims * sizeof(hsize_t))))
	 BAIL(NC_ENOMEM);
      if (!(chunksize = nc_malloc(var->ndims * sizeof(hsize_t))))
	 BAIL(NC_ENOMEM);
      for (d = 0; d < var->ndims; d++)
	 for (g = grp; g && (dims_found < var->ndims); g = g->parent)
	    for (dim = g->dim; dim; dim = dim->next)
	       if (dim->dimid == var->dimids[d]) 
	       {
		  dimsize[d] = dim->unlimited ? NC_HDF5_UNLIMITED_DIMSIZE : dim->len;
		  maxdimsize[d] = dim->unlimited ? H5S_UNLIMITED : (hsize_t)dim->len;
		  if (var->chunksizes[d])
		     chunksize[d] = var->chunksizes[d];
		  else 
		  {
		     chunksize[d] = (dim->unlimited) ? 1 : dim->len < NC_MAX_INT ? dim->len : NC_MAX_INT;
		     set_chunksizes++;
		  }
		  if (!var->contiguous && !var->chunksizes[d])
		     var->chunksizes[d] = chunksize[d];
		  dims_found++;
		  break;
	       }
      
      if (var->contiguous)
      {
	 if (H5Pset_layout(plistid, H5D_CONTIGUOUS) < 0)
	    BAIL(NC_EHDFERR);
      }
      else
      {
	 /* If the library had to set the chunksizes (i.e. the user
	  * didn't explicitly set them), then make sure no chunk
	  * contains more than 4 GB data. */
	 if (set_chunksizes)
	 {
	    int reduce = 1;
	    NC_TYPE_INFO_T *type_info;
	    if ((retval = nc4_get_typelen_mem(grp->file->nc4_info, var->xtype, 
					      0, &type_len)))
	       BAIL(retval);
	    if ((retval = nc4_find_type(grp->file->nc4_info, var->xtype, &type_info)))
	       BAIL(retval);
	    
	    while (reduce)
	    {
	       long long total;
	       if (type_info && type_info->class == NC_VLEN)
		  total = sizeof(hvl_t);
	       else
		  total = type_len;
	       for (d = 0; d < var->ndims; d++)
		  total *= var->chunksizes[d];

	       if (total < NC_MAX_UINT)
		  reduce = 0;
	       else
		  for (d = 0; d < var->ndims; d++)
		  {
		     var->chunksizes[d] /= 2;
		     chunksize[d] = var->chunksizes[d];
		  }
	    }
	 }
	 if (H5Pset_chunk(plistid, var->ndims, chunksize) < 0)
	    BAIL(NC_EHDFERR);
      }
   
      /* Create the dataspace. */
      if ((spaceid = H5Screate_simple(var->ndims, dimsize, maxdimsize)) < 0)
	 BAIL(NC_EHDFERR);
   }
   else
   {
      if ((spaceid = H5Screate(H5S_SCALAR)) < 0)
	 BAIL(NC_EHDFERR);
   }

   /* Turn on creation order tracking. */
   if (H5Pset_attr_creation_order(plistid, H5P_CRT_ORDER_TRACKED|
				  H5P_CRT_ORDER_INDEXED) < 0)
      BAIL(NC_EHDFERR);

   /* At long last, create the dataset. */
   LOG((4, "var_create_dataset: about to H5Dcreate dataset %s of type 0x%x", 
	var->name, typeid));
   if ((var->hdf_datasetid = H5Dcreate(grp->hdf_grpid, var->name, 
				       typeid, spaceid, plistid)) < 0)
      BAIL(NC_EHDFERR);
   var->created++;
   var->dirty = 0;

   /* If this is a dimscale, mark it as such in the HDF5 file. Also
    * find the dimension info and store the dataset id of the dimscale
    * dataset. */
   if (var->dimscale)
   {
      if (H5DSset_scale(var->hdf_datasetid, var->name) < 0)
	 BAIL(NC_EHDFERR);
      for (dim = grp->dim; dim; dim = dim->next)
	 if (strcmp(dim->name, var->name) == 0)
	 {
	    dim->hdf_dimscaleid = var->hdf_datasetid;
	    break;
	 }

      /* Make sure we found a dimension, and gave it a dimscale id. */
      if (!dim || !dim->hdf_dimscaleid)
	 BAIL(NC_EDIMMETA);
   }

  exit:
   if (dsid > 0 && H5Dclose(dsid) < 0)
      BAIL2(NC_EHDFERR);
   if (plistid > 0 && H5Pclose(plistid) < 0)
      BAIL2(NC_EHDFERR);
   if (spaceid > 0 && H5Sclose(spaceid) < 0)
      BAIL2(NC_EHDFERR);
   if (maxdimsize) nc_free(maxdimsize);
   if (dimsize) nc_free(dimsize);
   if (chunksize) nc_free(chunksize);
   if (fillp) nc_free(fillp);
   return retval;
}

/* Read or write an attribute. */
static int 
pg_att_grpa(NC_PG_T pg, NC_GRP_INFO_T *grp, int varid, NC_ATT_INFO_T *att)
{
   hid_t datasetid = 0, locid;
   hid_t attid = 0, spaceid = 0, file_typeid = 0;
   hsize_t dims[1]; /* netcdf attributes always 1-D. */
   int retval = NC_NOERR;
   void *data;
   int phoney_data = 99;
   size_t type_size;

   assert(att->name);
   LOG((3, "pg_att_grpa: pg %d varid %d att->attnum %d att->name %s "
	"att->xtype %d att->len %d", pg, varid, att->attnum, att->name,
	att->xtype, att->len));

   /* If the file is read-only, return an error. */
   if (pg == PUT && grp->file->nc4_info->no_write)
      return NC_EPERM;
   
   /* Get the hid to attach the attribute to, or read it from. */
   if (varid == NC_GLOBAL)
      locid = grp->hdf_grpid;
   else 
   {
      if ((retval = nc4_open_var_grp(grp, varid, &datasetid)))
	 BAIL(retval);
      locid = datasetid;
   }

   /* Caller wants to read the attribute from the file. */
   if (pg == GET)
   {
      int att_ndims;
      hssize_t att_npoints;
      H5T_class_t att_class;      
      hid_t native_typeid;
      
      /* Open the HDF5 attribute. */
      if ((attid = H5Aopen_name(locid, att->name)) < 0)
	 BAIL(NC_ENOTATT);

      /* Get type of attribute in file. */
      if ((file_typeid = H5Aget_type(attid)) < 0)
	 BAIL(NC_EATTMETA);
      if ((att_class = H5Tget_class(file_typeid)) < 0)
	 BAIL(NC_EATTMETA);
      if ((retval = get_netcdf_type(grp->file->nc4_info, file_typeid, &(att->xtype))))
	 BAIL(retval);

      /* Get len. */
      if ((spaceid = H5Aget_space(attid)) < 0)
	 BAIL(NC_EATTMETA); 
      if ((att_ndims = H5Sget_simple_extent_ndims(spaceid)) < 0)
	 BAIL(NC_EATTMETA);
      if ((att_npoints = H5Sget_simple_extent_npoints(spaceid)) < 0)
	 BAIL(NC_EATTMETA);

      /* If both att_ndims and att_npoints are zero, then this is a
       * zero length att. */
      if (att_ndims == 0 && att_npoints == 0)
      {
	 dims[0] = 0;
      }
      else if (att->xtype == NC_CHAR)
      {
	 /* NC_CHAR attributes are written as a scalar in HDF5, of type
	  * H5T_C_S1, of variable length. */
	 if (att_ndims == 0) 
	 {
	    if (!(dims[0] = H5Tget_size(file_typeid)))
	       BAIL(NC_EATTMETA);
	 }
	 else
	 {
	    /* This is really a string type! */
	    att->xtype = NC_STRING;
	    dims[0] = att_npoints;
	 }
      } 
      else
      {
	 /* All netcdf attributes are 1-D only. */
	 if (att_ndims != 1)
	    BAIL(NC_EATTMETA);

	 /* Read the size of this attribute. */
	 if (H5Sget_simple_extent_dims(spaceid, dims, NULL) < 0)
	    BAIL(NC_EATTMETA);
      }
      
      /* Tell the user what the length if this attribute is. */
      att->len = dims[0];

      /* Allocate some memory if the len is not zero, and read the
	 attribute. */
      if (dims[0])
      {
	 if ((retval = nc4_get_typelen_mem(grp->file->nc4_info, att->xtype, 0,
					   &type_size)))
	    return retval;
	 if (att_class == H5T_VLEN)
	 {
	    if ((native_typeid = H5Tget_native_type(file_typeid, H5T_DIR_DEFAULT)) < 0) 
	       return NC_EHDFERR;
	    if (!(att->vldata = nc_malloc((unsigned int)(att->len * sizeof(hvl_t)))))
	       BAIL(NC_ENOMEM);
	    if (H5Aread(attid, native_typeid, att->vldata) < 0)
	       BAIL(NC_EATTMETA);
	    if (H5Tclose(native_typeid) < 0)
	       BAIL(NC_EHDFERR);
	 }
	 else if (att->xtype == NC_STRING)
	 {
	    if (!(att->stdata = nc_calloc(att->len, sizeof(char *))))
	       BAIL(NC_ENOMEM);
	    if (H5Aread(attid, file_typeid, att->stdata) < 0)
	       BAIL(NC_EATTMETA);
	 }
	 else
	 {
	    if (!(att->data = nc_malloc((unsigned int)(att->len * type_size))))
	       BAIL(NC_ENOMEM);
	    if ((native_typeid = H5Tget_native_type(file_typeid, H5T_DIR_DEFAULT)) < 0) 
	       return NC_EHDFERR;
	    if (H5Aread(attid, native_typeid, att->data) < 0)
	       BAIL(NC_EATTMETA);
	    if (H5Tclose(native_typeid) < 0)
	       BAIL(NC_EHDFERR);
	 }
      }
      if (H5Tclose(file_typeid) < 0)
	 BAIL(NC_EHDFERR);
   }
   else /* We're putting (i.e. writing) the att */
   {
      /* Delete the att if it exists already. */
      if ((retval = nc4_delete_hdf5_att(locid, att->name)))
	 BAIL(retval);

      /* Get the length ready, and find the HDF type we'll be
       * writing. */
      dims[0] = att->len;
      if ((retval = get_hdf_typeid(grp->file->nc4_info, att->xtype, 
				   &file_typeid, 0)))
	 BAIL(retval);

      /* Even if the length is zero, HDF5 won't let me write with a
       * NULL pointer. So if the length of the att is zero, point to
       * some phoney data (which won't be written anyway.)*/
      if (!dims[0])
	 data = &phoney_data;
      else if (att->data)
	 data = att->data;
      else if (att->stdata)
	 data = att->stdata;
      else 
	 data = att->vldata;

      /* NC_CHAR types require some extra work. The space ID is set to
       * scalar, and the type is told how long the string is. If it's
       * really zero lenght, set the size to 1. (The fact that it's
       * really zero will be marked by the NULL dataspace, but HDF5
       * doens't allow me to set the size of the type to zero.)*/
      if (att->xtype == NC_CHAR)
      {
	 size_t string_size = dims[0];
	 if (!string_size)
	 {
	    string_size = 1;
	    if ((spaceid = H5Screate(H5S_NULL)) < 0) 
	       BAIL(NC_EATTMETA);
	 }
	 else
	 {
	    if ((spaceid = H5Screate(H5S_SCALAR)) < 0)
	       BAIL(NC_EATTMETA);
	 }
	 if (H5Tset_size(file_typeid, string_size) < 0)
	    BAIL(NC_EATTMETA);
	 if (H5Tset_strpad(file_typeid, H5T_STR_NULLTERM) < 0)
	    BAIL(NC_EATTMETA);
      }
      else
      {
	 if (!att->len)
	 {
	    if ((spaceid = H5Screate(H5S_NULL)) < 0) 
	       BAIL(NC_EATTMETA);
	 }
	 else
	 {
	    if ((spaceid = H5Screate_simple(1, dims, NULL)) < 0)
	       BAIL(NC_EATTMETA);
	 }
      }
      if ((attid = H5Acreate(locid, att->name, file_typeid, spaceid, 
			     H5P_DEFAULT)) < 0)
	 BAIL(NC_EATTMETA);

      /* Write the values, (even if length is zero). */
      if (H5Awrite(attid, file_typeid, data) < 0)
	 BAIL(NC_EATTMETA);
   }

  exit:
   if (datasetid > 0 && H5Dclose(datasetid) < 0)
      BAIL2(NC_EHDFERR);
   if (attid > 0 && H5Aclose(attid) < 0)
      BAIL2(NC_EHDFERR);
   if (spaceid > 0 && H5Sclose(spaceid) < 0)
      BAIL2(NC_EHDFERR);
   return retval;
}

/* Read information about a user defined type from the HDF5 file, and
 * stash it in the group's list of types. Return the netcdf typeid
 * through a pointer, if caller desires it. */
static int
read_type(NC_GRP_INFO_T *grp, char *type_name)
{
   NC_TYPE_INFO_T *type;
   H5T_class_t class;
   hid_t hdf_typeid, native_typeid;
   int nmembers;
   hid_t member_hdf_typeid, base_hdf_typeid = 0;
   char *member_name;
   size_t type_size = 0, member_offset;
   unsigned int m;
   nc_type ud_type_type = NC_NAT, base_nc_type = NC_NAT;
   htri_t ret;
   int retval = NC_NOERR;
   void *value;
   int i;

   assert(grp && type_name);

   if (strlen(type_name) > NC_MAX_NAME)
      return NC_EBADNAME;

   LOG((4, "read_type: type_name %s grp->name %s", type_name, grp->name));

   if ((hdf_typeid = H5Topen2(grp->hdf_grpid, type_name, H5P_DEFAULT)) < 0)
      BAIL(NC_EHDFERR);

   /* What is the class of this type, compound, vlen, etc. */
   if ((class = H5Tget_class(hdf_typeid)) < 0)
      return NC_EHDFERR;
   switch (class)
   {
      case H5T_STRING:
	 ud_type_type = NC_STRING;
	 break;
      case H5T_COMPOUND:
	 ud_type_type = NC_COMPOUND; 

	 /* What size is this type? */
	 if ((native_typeid = H5Tget_native_type(hdf_typeid, H5T_DIR_DEFAULT)) < 0) 
	    return NC_EHDFERR;
	 if (!(type_size = H5Tget_size(native_typeid)))
	    return NC_EHDFERR;
	 LOG((5, "type_size %d", type_size));
	 break;
      case H5T_VLEN:
	 /* For conveninence we allow user to pass vlens of strings
	  * with null terminated strings. This means strings are
	  * treated slightly differently by the API, although they are
	  * really just VLENs of characters. */
	 if ((ret = H5Tis_variable_str(hdf_typeid)) < 0)
	    return NC_EHDFERR;
	 if (ret)
	    ud_type_type = NC_STRING;
	 else
	 {
	    ud_type_type = NC_VLEN;
	    /* Find the base type of this vlen (i.e. what is this a
	     * vlen of?) */
	    if (!(base_hdf_typeid = H5Tget_super(hdf_typeid)))
	       return NC_EHDFERR;
	    /* What size is this type? */
	    if (!(type_size = H5Tget_size(base_hdf_typeid)))
	       return NC_EHDFERR;
	    /* What is the netcdf corresponding type. */
	    if ((retval = get_netcdf_type(grp->file->nc4_info, base_hdf_typeid, 
					  &base_nc_type)))
	       return retval;
	    LOG((5, "base_hdf_typeid 0x%x type_size %d base_nc_type %d", 
		 base_hdf_typeid, type_size, base_nc_type));
	 }
	 break;
      case H5T_OPAQUE:
	 ud_type_type = NC_OPAQUE;
	 /* What size is this type? */
	 if (!(type_size = H5Tget_size(hdf_typeid)))
	    return NC_EHDFERR;
	 LOG((5, "type_size %d", type_size));
	 break;
      case H5T_ENUM:
	 ud_type_type = NC_ENUM;

	 /* Find the base type of this enum (i.e. what is this a
	  * enum of?) */
	 if (!(base_hdf_typeid = H5Tget_super(hdf_typeid)))
	    return NC_EHDFERR;
	 /* What size is this type? */
	 if (!(type_size = H5Tget_size(base_hdf_typeid)))
	    return NC_EHDFERR;
	 /* What is the netcdf corresponding type. */
	 if ((retval = get_netcdf_type(grp->file->nc4_info, base_hdf_typeid, 
				       &base_nc_type)))
	    return retval;
	 LOG((5, "base_hdf_typeid 0x%x type_size %d base_nc_type %d", 
	      base_hdf_typeid, type_size, base_nc_type));
	 break;
      default:
	 LOG((0, "unknown class"));
	 return NC_EBADCLASS;
   }

   /* Add to the list for this new type, and get a local pointer to it. */
   if ((retval = nc4_type_list_add(&grp->type, grp->file->nc4_info->next_typeid, 
				   type_size, type_name, ud_type_type, base_nc_type)))
      return retval;
   if ((retval = nc4_find_type(grp->file->nc4_info, 
			   grp->file->nc4_info->next_typeid, &type)))
      return retval;
   assert(type);

   /* Increment this number so the next user defined type will get a
    * unique id. */
   grp->file->nc4_info->next_typeid++;

   /* Fill in struct with info about this type. */
   type->committed++;
   type->hdf_typeid = hdf_typeid;

   /* Read info about each member of this compound type. */
   if (ud_type_type == NC_COMPOUND)
   {
      if ((nmembers = H5Tget_nmembers(hdf_typeid)) < 0)
	 return NC_EHDFERR;
      LOG((5, "compound type has %d members", nmembers));
      for (m = 0; m < nmembers; m++)
      {
	 H5T_class_t mem_class;
	 int ndims = 0, dim_size[NC_MAX_DIMS];
	 hsize_t dims[NC_MAX_DIMS];
	 int d;
	 
	 if ((member_hdf_typeid = H5Tget_member_type(hdf_typeid, m)) < 0)
	    return NC_EHDFERR;
	 if ((mem_class = H5Tget_class(member_hdf_typeid)) < 0)
	    return NC_EHDFERR;
	 if (mem_class == H5T_ARRAY)
	 {
	    if ((ndims = H5Tget_array_ndims(member_hdf_typeid)) < 0)
	       return NC_EHDFERR;
	    if (H5Tget_array_dims(member_hdf_typeid, dims, NULL) != ndims)
	       return NC_EHDFERR;
	    for (d = 0; d < ndims; d++)
	       dim_size[d] = dims[d];
	 }
	 if (!(member_name = H5Tget_member_name(hdf_typeid, m)))
	    return NC_EHDFERR;
	 if ((member_offset = H5Tget_member_offset(hdf_typeid, m)) < 0)
	    return NC_EHDFERR;
	 if (!member_name || strlen(member_name) > NC_MAX_NAME)
	    return NC_EBADNAME;
	 if (ndims)
	 {
	    if ((retval = nc4_field_list_add(&type->field, type->num_fields++, member_name, 
					     member_offset, H5Tget_super(member_hdf_typeid), 
					     0, ndims, dim_size)))
	       return retval;
	 }
	 else
	 {
	    if ((retval = nc4_field_list_add(&type->field, type->num_fields++, member_name, 
					     member_offset, member_hdf_typeid, 0, 0, NULL)))
	       return retval;
	 } /* next member */
	 
	 /* HDF5 allocated this for us. */
	 free(member_name);
      }
   }
   else if (ud_type_type == NC_VLEN)
   {
      type->base_hdf_typeid = base_hdf_typeid;
   }
   else if (ud_type_type == NC_ENUM)
   {
      /* Remember the base HDF5 type for this enum. */
      type->base_hdf_typeid = base_hdf_typeid;

      /* Find out how many member are in the enum. */
      if ((type->num_enum_members = H5Tget_nmembers(hdf_typeid)) < 0) 
	 return NC_EHDFERR;

      /* Allocate space for one value. */
      if (!(value = nc_calloc(1, type_size)))
	 return NC_ENOMEM;

      /* Read each name and value defined in the enum. */
      for (i=0; i < type->num_enum_members; i++)
      {
	 /* Get the name and value from HDF5. */
	 if (!(member_name = H5Tget_member_name(hdf_typeid, i)))
	    return NC_EHDFERR;
	 if (!member_name || strlen(member_name) > NC_MAX_NAME)
	    return NC_EBADNAME;
	 if (H5Tget_member_value(hdf_typeid, i, value) < 0) 
	    return NC_EHDFERR;

	 /* Insert new field into this type's list of fields. */
	 if ((retval = nc4_enum_member_add(&type->enum_member, type->size, 
					   member_name, value)))
	    return retval;
      }
      
      /* Free the tempory memory for one value, and the member name
       * (which HDF5 allocated for us). */
      nc_free(value);
      free(member_name);
   }
   
  exit:
   return retval;
}
/* This will delete HDF5 attribute name from loc, if it exists. If the
   att doesn't exists, nothing will happen (and the function will
   return NC_NOERR). */
int
nc4_delete_hdf5_att(hid_t loc, const char *name)
{
   hid_t att = 0;
   char att_name[NC_MAX_HDF5_NAME + 1];
   int a, num, finished = 0;
   int retval = NC_NOERR;

   if ((num = H5Aget_num_attrs(loc)) < 0)
      return NC_EHDFERR;

   for (a = 0; a < num && !finished; a++) 
   {
      if ((att = H5Aopen_idx(loc, (unsigned int)a)) < 0)
	 BAIL(NC_EHDFERR);
      if (H5Aget_name(att, NC_MAX_HDF5_NAME, att_name) < 0)
	 BAIL(NC_EHDFERR);
      if (!strcmp(att_name, name))
      {
	 LOG((4, "nc4_delete_hdf5_att: deleting HDF5 att %s", name));
	 if (H5Adelete(loc, name) < 0)
	    BAIL(NC_EHDFERR);
	 finished++;
      }
      if (att > 0 && H5Aclose(att) < 0)
	 BAIL(NC_EHDFERR);
   }
   
  exit:
   return retval;
}

/* Create a HDF5 defined type from a NC_TYPE_INFO_T struct, and commit
 * it to the file. */
static int
commit_type(NC_GRP_INFO_T *grp, NC_TYPE_INFO_T *type)
{
   NC_FIELD_INFO_T *field;
   NC_ENUM_MEMBER_INFO_T *enum_m;
   hid_t hdf_base_typeid, hdf_typeid;
   int retval;

   assert(grp && type);

   /* Did we already record this type? */
   if (type->committed) 
      return NC_NOERR;
   
   /* Is this a compound type? */
   if (type->class == NC_COMPOUND)
   {
      if ((type->hdf_typeid = H5Tcreate(H5T_COMPOUND, type->size)) < 0)
	 return NC_EHDFERR;
      LOG((4, "creating compound type %s hdf_typeid 0x%x", type->name, 
	   type->hdf_typeid));
      for (field = type->field; field; field = field->next)
      {
	 if ((retval = get_hdf_typeid(grp->file->nc4_info, field->nctype, 
				      &hdf_base_typeid, type->endianness)))
	    return retval;
	 /* If this is an array, create a special array type. */
	 if (field->ndims)
	 {
	    int d;
	    hsize_t dims[NC_MAX_DIMS];
	    for (d = 0; d < field->ndims; d++)
	       dims[d] = field->dim_size[d];
	    if ((hdf_typeid = H5Tarray_create(hdf_base_typeid, field->ndims, 
					      dims, NULL)) < 0)
	       return NC_EHDFERR;
	 } 
	 else
	    hdf_typeid = hdf_base_typeid;
	 LOG((4, "inserting field %s offset %d hdf_typeid 0x%x", field->name, 
	      field->offset, hdf_typeid));
	 if (H5Tinsert(type->hdf_typeid, field->name, field->offset, 
		       hdf_typeid) < 0)
	    return NC_EHDFERR;
	 if (field->ndims && H5Tclose(hdf_typeid) < 0)
	    return NC_EHDFERR;
      }
   } 
   else if (type->class == NC_VLEN)
   {
      /* Find the HDF typeid of the base type of this vlen. */
      if ((retval = get_hdf_typeid(grp->file->nc4_info, type->base_nc_type, 
				   &type->base_hdf_typeid, type->endianness)))
	 return retval;

      /* Create a vlen type. */
      if ((type->hdf_typeid = H5Tvlen_create(type->base_hdf_typeid)) < 0)
	 return NC_EHDFERR;
   } 
   else if (type->class == NC_OPAQUE)
   {
      /* Create the opaque type. */
      if ((type->hdf_typeid = H5Tcreate(H5T_OPAQUE, type->size)) < 0)
	 return NC_EHDFERR;
   } 
   else if (type->class == NC_ENUM)
   {
      if (!type->enum_member)
	 return NC_EINVAL;

      /* Find the HDF typeid of the base type of this enum. */
      if ((retval = get_hdf_typeid(grp->file->nc4_info, type->base_nc_type, 
				   &type->base_hdf_typeid, type->endianness)))
	 return retval;
      
      /* Create an enum type. */
      if ((type->hdf_typeid =  H5Tenum_create(type->base_hdf_typeid)) < 0) 
	 return NC_EHDFERR;
      
      /* Add all the members to the HDF5 type. */
      for (enum_m = type->enum_member; enum_m; enum_m = enum_m->next)	
	 if (H5Tenum_insert(type->hdf_typeid, enum_m->name, 
			    enum_m->value) < 0) 
	    return NC_EHDFERR;
   } 
   else
   {
      LOG((0, "Unknown class: %d", type->class));
      return NC_EBADTYPE;
   }
      
   if (H5Tcommit(grp->hdf_grpid, type->name, type->hdf_typeid) < 0)
      return NC_EHDFERR;
   type->committed++;
   LOG((4, "just committed type %s, HDF typeid: 0x%x", type->name, 
	type->hdf_typeid));

   return NC_NOERR;
}

/* Write an attribute, with value 1, to indicate that strict NC3 rules
 * apply to this file. */
static int
write_nc3_strict_att(hid_t hdf_grpid)
{
   hid_t attid, spaceid;
   int one = 1;
   int retval = NC_NOERR;

   /* If the attribute already exists, call that a success. */
   if ((attid = H5Aopen_name(hdf_grpid, NC3_STRICT_ATT_NAME)) >= 0)
   {
      if (H5Aclose(attid) < 0)
	 return NC_EFILEMETA;
      return NC_NOERR;
   }

   /* Create the attribute to mark this as a file that needs to obey
    * strict netcdf-3 rules. */
   if ((spaceid = H5Screate(H5S_SCALAR)) < 0)
      BAIL(NC_EFILEMETA);
   if ((attid = H5Acreate(hdf_grpid, NC3_STRICT_ATT_NAME, 
			  H5T_NATIVE_INT, spaceid, H5P_DEFAULT)) < 0)
      BAIL(NC_EFILEMETA);
   if (H5Awrite(attid, H5T_NATIVE_INT, &one) < 0)
      BAIL(NC_EFILEMETA);

  exit:
   if (spaceid && (H5Sclose(spaceid) < 0))
      BAIL2(NC_EFILEMETA);
   if (attid && (H5Aclose(attid) < 0))
      BAIL2(NC_EFILEMETA);
   return retval;
}

static int
create_group(NC_GRP_INFO_T *grp)
{
   hid_t gcpl_id = 0;
   int retval = NC_NOERR;;

   assert(grp);

   /* If this is not the root group, create it in the HDF5 file. */
   if (grp->parent)
   {
      /* Create group, with link_creation_order set in the group
       * creation property list. */
      if ((gcpl_id = H5Pcreate(H5P_GROUP_CREATE)) < 0)
	 return NC_EHDFERR;
      if (H5Pset_link_creation_order(gcpl_id, H5P_CRT_ORDER_TRACKED|H5P_CRT_ORDER_INDEXED) < 0)
	 BAIL(NC_EHDFERR);
      if (H5Pset_attr_creation_order(gcpl_id, H5P_CRT_ORDER_TRACKED|H5P_CRT_ORDER_INDEXED) < 0)
	 BAIL(NC_EHDFERR);

/*      if ((grp->hdf_grpid = H5Gcreate_anon(grp->parent->hdf_grpid, 
					   gcpl_id, H5P_DEFAULT)) < 0)
	 BAIL(NC_EHDFERR);
      if ((H5Olink(grp->hdf_grpid, grp->parent->hdf_grpid, grp->name, 
		   H5P_DEFAULT, H5P_DEFAULT)) < 0)
		   BAIL(NC_EHDFERR);*/
      if ((grp->hdf_grpid = H5Gcreate2(grp->parent->hdf_grpid, grp->name,  
				       H5P_DEFAULT, gcpl_id, H5P_DEFAULT)) < 0)
		BAIL(NC_EHDFERR);

      if (H5Pclose(gcpl_id) < 0)
	 BAIL(NC_EHDFERR);
   }
   else
   {
      /* Since this is the root group, we just have to open it. */
      if ((grp->hdf_grpid = H5Gopen2(grp->file->nc4_info->hdfid, "/", H5P_DEFAULT)) < 0)
	 BAIL(NC_EFILEMETA);
   }
   assert(grp->hdf_grpid > 0);
   return NC_NOERR;

  exit:
   if (gcpl_id > 0 && H5Pclose(gcpl_id) < 0)
      BAIL2(NC_EHDFERR);
   if (grp->hdf_grpid > 0 && H5Gclose(grp->hdf_grpid) < 0)
      BAIL2(NC_EHDFERR);
   return retval;
}

static int
attach_dimscales(NC_GRP_INFO_T *grp)
{
   NC_VAR_INFO_T *var;
   NC_DIM_INFO_T *dim1;
   NC_GRP_INFO_T *g;    
   int d;
   int retval = NC_NOERR;

   /* Attach dimension scales. */
   for (var = grp->var; var; var = var->next)
   {
      /* Scales themselves do not attach. */
      if (var->dimscale) continue;

      /* Find the scale for each dimension and attach it. */
      for (d = 0; d < var->ndims; d++)
      {
	 assert(var->dimscale_attached);
	 if (!var->dimscale_attached[d])
	 {
	    for (g = grp; g && !var->dimscale_attached[d]; g = g->parent)
	       for (dim1 = g->dim; dim1; dim1 = dim1->next)
		  if (var->dimids[d] == dim1->dimid)
		  {
		     LOG((2, "attach_dimscales: attaching scale for dimid %d to var %s", 
			  var->dimids[d], var->name));
		     if (H5DSattach_scale(var->hdf_datasetid, dim1->hdf_dimscaleid, d) < 0)
			BAIL(NC_EHDFERR);
		     var->dimscale_attached[d]++;
		     break;
		  }
	 }

	 /* If we didn't find a dimscale to attach, that's a problem! */
	 if (!var->dimscale_attached[d])
	 {
	    LOG((0, "no dimscale found!"));
	    return NC_EDIMSCALE;
	 }
      } /* next d */
   }
  exit:
   return retval;
}

/* Write all the dirty atts in an attlist. */
static int
write_attlist(NC_ATT_INFO_T *attlist, int varid, NC_GRP_INFO_T *grp)
{
   NC_ATT_INFO_T *att;
   int retval;

   for (att = attlist; att; att = att->next)
   {
      if (att->dirty)
      {
	 LOG((4, "write_attlist: writing att %s to varid %d", att->name, varid));
	 if ((retval = pg_att_grpa(PUT, grp, varid, att)))
	    return retval;
	 att->dirty = 0;
	 att->created++;
      }
   }
   return NC_NOERR;
}

static int
write_var(NC_VAR_INFO_T *var, NC_GRP_INFO_T *grp)
{
   NC_DIM_INFO_T *d1 = NULL;
   int replace_existing_var = 0;
   int retval;

   if (var->dirty)
   {
      LOG((4, "nc4_rec_write_metadata: writing var %s", var->name));

      if (var->created)
	 replace_existing_var = 1;

      /* If this is a coordinate var, and a dataset has already
       * been created for it, then delete that dataset and recreate
       * it (because it's type may be wrong anyway.) But then we
       * have to reattach dimension scales for all vars! Oh well,
       * this all only happens when the user defines a var, writes
       * metadata, reenters define mode, and adds a coordinate
       * var. Presumably this will happen rarely. */

      /* Is this a coordinate var that has already been created in
       * the HDF5 as a dimscale dataset? Check for dims with the
       * same name in this group. If there is one, check to see if
       * this object exists in the HDF group. */
      if (var->dimscale)
	 for (d1 = grp->dim; d1; d1 = d1->next)
	    if (!strcmp(d1->name, var->name))
	    {
	       H5G_stat_t info;
	       if (H5Gget_objinfo(grp->hdf_grpid, var->name, 1, &info) >= 0)
	       {
		  replace_existing_var++;

		  /* If we're replacing an existing dimscale dataset, go to
		   * every var in the file and detatch this dimension scale,
		   * because we have to delete it. */
		  if ((retval = rec_detach_scales(grp->file->nc4_info->root_grp, 
						  var->dimids[0], d1->hdf_dimscaleid)))
		     return retval;
		  break;
	       }
	    }
	 
      /* Delete the HDF5 dataset that is to be replaced. */
      if (replace_existing_var)
      {
	 /* If this is a dimension scale, do this stuff. */
	 if (d1)
	 {
	    assert(d1 && d1->hdf_dimscaleid);
	    if (H5Dclose(d1->hdf_dimscaleid) < 0) 
	       return NC_EDIMMETA;
	 }
	 else
	 {
	    int dims_detached = 0;
	    int finished = 0;
	    int d;
	    NC_DIM_INFO_T *dim1;
	    NC_GRP_INFO_T *g;

	    /* If this is a regular var, detach all it's dim scales. */
	    for (d = 0; d < var->ndims; d++)
	       for (g = grp; g && !finished; g = g->parent)
		  for (dim1 = g->dim; dim1; dim1 = dim1->next)
		     if (var->dimids[d] == dim1->dimid)
		     {
			if (H5DSdetach_scale(var->hdf_datasetid, dim1->hdf_dimscaleid, d) < 0)
			   BAIL(NC_EHDFERR);
			var->dimscale_attached[d] = 0;
			if (dims_detached++ == var->ndims)
			   finished++;
		     }
	 }

	 /* Free the HDF5 dataset id. */
	 if (var->hdf_datasetid && H5Dclose(var->hdf_datasetid)) 
	    BAIL(NC_EHDFERR);
	       
	 /* Now delete the variable. */
	 if (H5Gunlink(grp->hdf_grpid, var->name) < 0)
	    return NC_EDIMMETA;
      }

      /* Create the dataset. */
      if ((retval = var_create_dataset(grp, var)))
	 return retval;
	 
      /* Reattach this scale everywhere it is used. (Recall that
       * netCDF dimscales are always 1-D). */
      if (d1 && replace_existing_var)
      {
	 d1->hdf_dimscaleid = var->hdf_datasetid;
	 if ((retval = rec_reattach_scales(grp->file->nc4_info->root_grp, 
					   var->dimids[0], d1->hdf_dimscaleid)))
	    return retval;
      }
   }
	 
   /* Now check the atributes for this var. */
   /* Write attributes for this var. */
   if ((retval = write_attlist(var->att, var->varid, grp)))
      BAIL(retval);
   
   return NC_NOERR;
  exit:
   return retval;
}

static int
write_dim(NC_DIM_INFO_T *dim, NC_GRP_INFO_T *grp)
{
   hid_t spaceid, create_propid;
   hsize_t dims[1], max_dims[1], chunk_dims[1] = {1}; 
   int dimscale_exists = 0;
   char dimscale_wo_var[NC_MAX_NAME];
   int retval;

   if (dim->dirty)
   {
/*       /\* Do we already have a dimscale variable? The name must be */
/*        * identical. If so, we don't need to do anything. *\/ */
/*       for (dimscale_exists = 0, var = grp->var; var; var = var->next) */
/* 	 if (strcmp(var->name, dim->name) == 0) */
/* 	 { */
/* 	    dimscale_exists++; */
/* 	    if ((retval = write_var(var, grp))) */
/* 	       BAIL(retval); */
/* 	    break; */
/* 	 } */

      /* If there's no dimscale dataset for this dim, create one,
       * and mark that it should be hidden from netCDF as a
       * variable. (That is, it should appear as a dimension
       * without an associated variable.) */
      if (!dimscale_exists)
      {
	 LOG((4, "write_dim: creating dim %s", dim->name));

	 /* Create a property list. If this dimension scale is
	  * unlimited (i.e. it's an unlimited dimension), then set
	  * up chunking, with a chunksize of 1. */
	 if ((create_propid = H5Pcreate(H5P_DATASET_CREATE)) < 0)
	    BAIL(NC_EHDFERR);
	 dims[0] = dim->len;
	 max_dims[0] = dim->len;
	 if (dim->unlimited) 
	 {
	    max_dims[0] = H5S_UNLIMITED;
	    if (H5Pset_chunk(create_propid, 1, chunk_dims) < 0)
	       BAIL(NC_EHDFERR);
	 }

	 /* Set up space. */
	 if ((spaceid = H5Screate_simple(1, dims, max_dims)) < 0) 
	    BAIL(NC_EHDFERR);

	 /* If we define, and then rename this dimension before
	  * creation of the dimscale dataset, then we can throw
	  * away the old_name of the dimension. */
	 if (strlen(dim->old_name))
	    strcpy(dim->old_name, "");

	 if (H5Pset_attr_creation_order(create_propid, H5P_CRT_ORDER_TRACKED|
					H5P_CRT_ORDER_INDEXED) < 0)
	    BAIL(NC_EHDFERR);

	 /* Create the dataset that will be the dimension scale. */
	 LOG((4, "write_dim: about to H5Dcreate a dimscale dataset %s", dim->name));
	 if ((dim->hdf_dimscaleid = H5Dcreate(grp->hdf_grpid, dim->name, H5T_IEEE_F32BE, 
					      spaceid, create_propid)) < 0)
	    BAIL(NC_EHDFERR);

	 /* Close the spaceid and create_propid. */
	 if (H5Sclose(spaceid) < 0)
	    BAIL(NC_EHDFERR);
	 if (H5Pclose(create_propid) < 0)
	    BAIL(NC_EHDFERR);

	 /* Indicate that this is a scale. Also indicate that not
	  * be shown to the user as a variable. It is hidden. It is
	  * a DIM WITHOUT A VARIABLE! */
	 sprintf(dimscale_wo_var, "%s%10d", DIM_WITHOUT_VARIABLE, dim->len);
	 if (H5DSset_scale(dim->hdf_dimscaleid, dimscale_wo_var) < 0)
	    BAIL(NC_EHDFERR);
      }
      dim->dirty = 0;
   }
   
   /* Did we extend an unlimited dimension? */
   if (dim->extended)
   {
      NC_VAR_INFO_T *v1;
      hsize_t new_size;

      assert(dim->unlimited);
      /* If this is a dimension without a variable, then update
       * the secret length information at the end of the NAME
       * attribute. */
      for (v1 = grp->var; v1; v1 = v1->next)
	 if (!strcmp(v1->name, dim->name))
	    break;
	 
      if (!v1)
      {
/*	 sprintf(dimscale_wo_var, "%s%10d", DIM_WITHOUT_VARIABLE, dim->len);
	 if (H5DSset_scale(dim->hdf_dimscaleid, dimscale_wo_var) < 0)
	 BAIL(NC_EHDFERR);*/
      }
      else
      {
	 /* Extend the dimension scale dataset to reflect the new
	  * length of the dimension. */
	 new_size = dim->len;
	 if (H5Dextend(v1->hdf_datasetid, &new_size) < 0)
	    BAIL(NC_EHDFERR);
      }
   }

   /* Did we rename this dimension? */
   if (strlen(dim->old_name))
   {
      /* Rename the dimension's dataset in the HDF5 file. */
      if (H5Gmove2(grp->hdf_grpid, dim->old_name, grp->hdf_grpid, dim->name) < 0)
	 return NC_EHDFERR;
	 
      /* Reset old_name. */
      strcpy(dim->old_name, "");
   }

   return NC_NOERR;
  exit:
   return retval;
}

/* Recursively write all the metadata in a group. */
int
nc4_rec_write_metadata(NC_GRP_INFO_T *grp)
{
   NC_DIM_INFO_T *dim;
   NC_VAR_INFO_T *var;
   NC_GRP_INFO_T *child_grp;
   NC_TYPE_INFO_T *type;
   int found_coord, coord_varid, wrote_coord;
   int retval;

   assert(grp && grp->name);
   LOG((3, "nc4_rec_write_metadata: grp->name %s", grp->name));

   /* Create the group in the HDF5 file if it doesn't exist. */
   if (!grp->hdf_grpid)
      if ((retval = create_group(grp)))
	 return retval;

   /* If this is the root group of a file with strict NC3 rules, write
    * an attribute. But don't leave the attribute open. */
   if (!grp->parent && (grp->file->nc4_info->cmode & NC_CLASSIC_MODEL))
      if ((retval = write_nc3_strict_att(grp->hdf_grpid)))
	 BAIL(retval);

   /* If there are any user-defined types, write them now. */
   for (type = grp->type; type; type = type->next)
      if ((retval = commit_type(grp, type)))
	 BAIL(retval);

   /* Write global attributes for this group. */
   if ((retval = write_attlist(grp->att, NC_GLOBAL, grp)))
      BAIL(retval);

   /*   for (var=nc->nc4_info->var; var; var = var->next)
	printf("var: %s ndims: %d\n", var->name, var->ndims);*/

   /* Set the pointer to the beginning of the list of vars in this
    * group. */
   var = grp->var;

   /* For some stupid reason, the dim list is stored backwards! Get to
    * the back of the list. */
   for (dim = grp->dim; dim && dim->next; dim = dim->next)
      ;

   /* Because of HDF5 ordering the dims and vars have to be stored in
    * this way to ensure that the dims and coordinate vars come out in
    * the correct order. (If the user writes coord vars in a different
    * order then he defined their dimensions, then the order of the
    * dimids will change to match the order of the coord vars. Is that
    * too bad? Or can we live with it?) */
   while (dim || var)
   {
      /* Write non-coord dims in order, stopping at the first one that
       * has an associated coord var. */
      for (found_coord = 0; dim && !found_coord; dim = dim->prev)
      {
	 if (!dim->coord_var)
	 {
	    if ((retval = write_dim(dim, grp)))
	       BAIL(retval);
	 }
	 else
	 {
	    found_coord++;
	    coord_varid = dim->coord_var->varid;
	 }
      }

      /* Write each var. When we get to the coord var we are waiting
       * for (if any), then we break after writing it. */
      for (wrote_coord = 0; var && !wrote_coord; var = var->next)
      {
	 if ((retval = write_var(var, grp)))
	    BAIL(retval);
	 if (found_coord && var->varid == coord_varid)
	    wrote_coord++;
      }
   } /* end while */

   if ((retval = attach_dimscales(grp)))
      BAIL(retval);
   
   /* If there are any child groups, write their metadata. */
   for (child_grp = grp->children; child_grp; child_grp = child_grp->next)
      if ((retval = nc4_rec_write_metadata(child_grp)))
	 return retval;
      
   return NC_NOERR;

  exit:
   return retval;
}

/* This reads/writes a whole var at a time. If the file has an
   unlimited dimension, then we will look at the number of records
   currently existing for this var, and read/write that many. This
   this is not what the user intended, particularly with writing, then
   that is there look-out! So we will not be extending datasets
   here. */
int
pg_var(NC_PG_T pg, NC_FILE_INFO_T *nc, int ncid, int varid, nc_type xtype, 
       int is_long, void *ip)
{
   NC_GRP_INFO_T *grp;
   NC_VAR_INFO_T *var;
   size_t start[NC_MAX_DIMS], count[NC_MAX_DIMS];
   int i;
   int retval;

   assert(nc);
   if ((retval = nc4_find_g_var_nc(nc, ncid, varid, &grp, &var)))
      return retval;
   assert(grp && var && var->name);

   /* For each dimension, the start will be 0, and the count will be
    * the length of the dimension. */
   for (i = 0; i < var->ndims; i++)
   {
      start[i] = 0;
      if ((retval = nc_inq_dimlen(ncid, var->dimids[i], &(count[i]))))
	 return retval;
   }

   return nc4_pg_vara(pg, nc, ncid, varid, start, count, xtype, is_long, ip);
}

/* Write or read some mapped data. Yea, like I even understand what it
   is!  

   I stole this code, lock, stock, and semicolons, from the netcdf
   3.5.1 beta release. It walks through the stride and map arrays, and
   converts them to a series of calles to the varm function.

   I had to modify the code a little to fit it in, and generalize it
   for all data types, and for both puts and gets.

   Ed Hartnett, 9/43/03
*/
int 
nc4_pg_varm(NC_PG_T pg, NC_FILE_INFO_T *nc, int ncid, int varid, const size_t *start, 
	    const size_t *edges, const ptrdiff_t *stride,
	    const ptrdiff_t *map, nc_type xtype, int is_long, void *data)
{
   NC_GRP_INFO_T *grp;
   NC_HDF5_FILE_INFO_T *h5;
   NC_VAR_INFO_T *var;
   int maxidim;    /* maximum dimensional index */
   size_t mem_type_size;
   int convert_map = 0;
   ptrdiff_t new_map[NC_MAX_DIMS];
   int i;
   int retval = NC_NOERR;

   LOG((3, "nc4_pg_varm: ncid 0x%x varid %d xtype %d", ncid, varid, 
	xtype));

   /* Find metadata for this file and var. */
   assert(nc && nc->nc4_info);
   h5 = nc->nc4_info;
   if ((retval = nc4_find_g_var_nc(nc, ncid, varid, &grp, &var)))
      return retval;
   assert(grp && var && var->name);

   /* If mem_nc_type is NC_NAT, it means we were called by
    * nc_get|put_varm, the old V2 API call! In this case we want to
    * use the file type as the mem type as well. Also, for these two
    * functions only, we interpret the map array as referring to
    * numbers of bytes rather than number of elements. (This is
    * something that changed between V2 and V3.) Also we do not allow
    * mapped access to user-defined vars in nc4. */
   if (xtype == NC_NAT)
   {
      if (var->xtype > NC_STRING)
	 return NC_EMAPTYPE;
      xtype = var->xtype;
      convert_map++;
   }
   assert(xtype);

   /* What is the size of this type? */
   if ((retval = nc4_get_typelen_mem(h5, xtype, is_long, &mem_type_size)))
      return retval;

   if(map != NULL && var->ndims && convert_map)
   {
      /* convert map units from bytes to units of sizeof(type) */
      for(i = 0; i < var->ndims; i++)
      {
	 if(map[i] % mem_type_size != 0)	
	    return NC_EINVAL;
	 new_map[i] = map[i] / mem_type_size;
      }
      map = new_map;
   }

   /* No text to number hanky-panky is allowed for those observing
    * strict netcdf-3 rules! It's sick. */
   if ((h5->cmode & NC_CLASSIC_MODEL) && (xtype == NC_CHAR || var->xtype == NC_CHAR) &&
       (xtype != var->xtype))
      return NC_ECHAR;

   /* If the file is read-only, return an error. */
   if (pg == PUT && h5->no_write)
      return NC_EPERM;

   /* If we're in define mode, we can't read or write data. If strict
    * nc3 rules are in effect, return an error, otherwise leave define
    * mode. */
   if (h5->flags & NC_INDEF)
   {
      if (h5->cmode & NC_CLASSIC_MODEL)
	 return NC_EINDEFINE;
      if ((retval = nc_enddef(ncid)))
	 BAIL(retval);
   }

#ifdef LOGGING
   {
      int i;
      if (start)
	 for (i=0; i<var->ndims; i++)
	    LOG((4, "start[%d] %d", i, start[i]));
      if (edges)
	 for (i=0; i<var->ndims; i++)
	    LOG((4, "edges[%d] %d", i, edges[i]));
      if (stride)
	 for (i=0; i<var->ndims; i++)
	    LOG((4, "stride[%d] %d", i, stride[i]));
      if (map)
	 for (i=0; i<var->ndims; i++)
	    LOG((4, "map[%d] %d", i, map[i]));
   }
#endif /* LOGGING */

   /* The code below was stolen from netcdf-3. Some comments by Ed. */
   maxidim = (int) var->ndims - 1;
   if (maxidim < 0)
   {
      /* The variable is a scalar; consequently, there is only one
	 thing to get and only one place to put it.  (Why was I
	 called?) */
      return pg_var(pg, nc, ncid, varid, xtype, is_long, data);
   }
        
   /* The variable is an array.  */
   {
      int idim;
      size_t *mystart = NULL;
      size_t *myedges;
      size_t *iocount;        /* count vector */
      size_t *stop;   /* stop indexes */
      size_t *length; /* edge lengths in bytes */
      ptrdiff_t *mystride;
      ptrdiff_t *mymap;

      /* Verify stride argument. */
      for (idim = 0; idim <= maxidim; ++idim)
      {
	 if (stride != NULL
	     && (stride[idim] == 0
		 /* cast needed for braindead systems with signed size_t */
		 || (unsigned long) stride[idim] >= X_INT_MAX))
	 {
	    return NC_ESTRIDE;
	 }
      }

      /* The mystart array of pointer info is needed to walk our way
	 through the dimensions as specified by the start, edges,
	 stride and (gulp!) map parameters. */
      if (!(mystart = (size_t *)nc_calloc((size_t)var->ndims * 7, sizeof(ptrdiff_t))))
	 return NC_ENOMEM;
      myedges = mystart + var->ndims;
      iocount = myedges + var->ndims;
      stop = iocount + var->ndims;
      length = stop + var->ndims;
      mystride = (ptrdiff_t *)(length + var->ndims);
      mymap = mystride + var->ndims;

      /* Initialize I/O parameters. */
      for (idim = maxidim; idim >= 0; --idim)
      {
	 /* Get start value, use 0 if non provided. */
	 mystart[idim] = start != NULL ? start[idim] : 0;

	 /* If any edges are 0, return NC_NOERR and forget it. */
	 if (edges[idim] == 0)
	 {
	    retval = NC_NOERR;
	    goto done;
	 }

	 /* If edges not provided, use the current dimlen. */
	 if (edges)
	    myedges[idim] = edges[idim];
	 else 
	 {
	    size_t len;
	    if ((retval = nc_inq_dimlen(ncid, var->dimids[idim], &len)))
	       goto done;
	    myedges[idim] = len - mystart[idim];
	 }
	 
	 /* If stride not provided, use 1. */
	 mystride[idim] = stride != NULL ? stride[idim] : 1;

	 /* If map is not provided, do something dark and
	    mysterious. */
	 if (map)
	    mymap[idim] = map[idim];
	 else
	    mymap[idim] = idim == maxidim ? 1 : 
	       mymap[idim + 1] * (ptrdiff_t) myedges[idim + 1];

	 iocount[idim] = 1;
	 length[idim] = mymap[idim] * myedges[idim];
	 stop[idim] = mystart[idim] + myedges[idim] * mystride[idim];
      }

      /* Check start, edges */
      for (idim = maxidim; idim >= 0; --idim)
      {
	 size_t dimlen;
	 if ((retval = nc_inq_dimlen(ncid, var->dimids[idim], &dimlen)))
	    goto done;
	 /* Don't check unlimited dimension on PUTs. */
	 if (pg == PUT)
	 {
	    int stop = 0, d, num_unlim_dim, unlim_dimids[NC_MAX_DIMS];
	    if ((retval = nc_inq_unlimdims(ncid, &num_unlim_dim, unlim_dimids)))
	       goto done;
	    for (d = 0; d < num_unlim_dim; d++)
	       if (var->dimids[idim] == unlim_dimids[d])
		  stop++;
	    if (stop)
	       break;
	 }
	 LOG((4, "idim=%d mystart[idim]=%d myedge[idim]=%d dimlen=%d", 
	      idim, mystart[idim], myedges[idim], dimlen));
	 if (mystart[idim] >= dimlen)
	 {
	    retval = NC_EINVALCOORDS;
	    goto done;
	 }
	 
	 if (mystart[idim] + myedges[idim] > dimlen)
	 {
	    retval = NC_EEDGE;
	    goto done;
	 }
      }

      /* OK, now we're just getting too fancy... As an optimization,
	 adjust I/O parameters when the fastest dimension has unity
	 stride both externally and internally. In this case, the user
	 could have called a simpler routine
	 (i.e. ncvarnc_get_vara_text).*/
      if (mystride[maxidim] == 1
	  && mymap[maxidim] == 1)
      {
	 iocount[maxidim] = myedges[maxidim];
	 mystride[maxidim] = (ptrdiff_t) myedges[maxidim];
	 mymap[maxidim] = (ptrdiff_t) length[maxidim];
      }

      /* Perform I/O.  Exit when done. */
      for (;;)
      {
	 int lretval = nc4_pg_vara(pg, nc, ncid, varid, mystart, iocount, xtype, 
				   is_long, data);
	 if (lretval != NC_NOERR 
	     && (retval == NC_NOERR || lretval != NC_ERANGE))
	    retval = lretval;

	 /*
	  * The following code permutes through the variable s
	  * external start-index space and it s internal address
	  * space.  At the UPC, this algorithm is commonly
	  * called "odometer code".
	  */
	 idim = maxidim;
	carry:
	 data = (char *)data + (mymap[idim] * mem_type_size);
	 LOG((4, "data=0x%x mymap[%d]=%d", data, idim, (int)mymap[idim]));
	 mystart[idim] += mystride[idim];
	 LOG((4, "mystart[%d]=%d length[%d]=%d", idim, (int)mystart[idim], 
	      idim, (int)length[idim]));
	 if (mystart[idim] == stop[idim])
	 {
	    mystart[idim] = start[idim];
	    data = (char *)data - (length[idim] * mem_type_size);
	    if (--idim < 0)
	       break; /* normal return */
	    goto carry;
	 }
      } /* I/O loop */
     done:
      nc_free(mystart);
   } /* variable is array */

  exit:   
   return retval;
}

/* This function will copy data from one buffer to another, in
   accordance with the types. Range errors will be noted, and the fill
   value used (or the default fill value if none is supplied) for
   values that overflow the type.

   I should be able to take this out when HDF5 does the right thing
   with data type conversion.

   Ed Hartnett, 11/15/3
*/

int
nc4_convert_type(const void *src, void *dest, 
	     const nc_type src_type, const nc_type dest_type, 
	     const size_t len, int *range_error, 
	     const void *fill_value, int strict_nc3, int src_long, 
	     int dest_long)
{
   char *cp, *cp1;
   float *fp, *fp1;
   double *dp, *dp1;
   int *ip, *ip1;
   signed long *lp, *lp1;
   short *sp, *sp1;
   signed char *bp, *bp1;
   unsigned char *ubp, *ubp1;
   unsigned short *usp, *usp1;
   unsigned int *uip, *uip1;
   long long *lip, *lip1;
   unsigned long long *ulip, *ulip1;
   size_t count = 0;

   *range_error = 0;
   LOG((3, "nc4_convert_type: len %d src_type %d dest_type %d src_long %d"
	" dest_long %d", len, src_type, dest_type, src_long, dest_long));

   /* OK, this is ugly. If you can think of anything better, I'm open
      to suggestions! 

      Note that we don't use a default fill value for type
      NC_BYTE. This is because Lord Voldemort cast a nofilleramous spell
      at Harry Potter, but it bounced off his scar and hit the netcdf-4
      code.
   */
   switch (src_type)
   {
      case NC_CHAR:
	 switch (dest_type)
	 {
	    case NC_CHAR:
	       for (cp = (char *)src, cp1 = dest; count < len; count++)
		  *cp1++ = *cp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: Uknown destination type."));
	 }
	 break;
      case NC_BYTE:
	 switch (dest_type)
	 {
	    case NC_BYTE:
	       for (bp = (signed char *)src, bp1 = dest; count < len; count++)
		  *bp1++ = *bp++;
	       break;
	    case NC_UBYTE:
	       for (bp = (signed char *)src, ubp = dest; count < len; count++)
	       {
		  if (*bp < 0)
		     (*range_error)++;
		  *ubp++ = *bp++;
	       }
	       break;
	    case NC_SHORT:
	       for (bp = (signed char *)src, sp = dest; count < len; count++)
		  *sp++ = *bp++;
	       break;
	    case NC_USHORT:
	       for (bp = (signed char *)src, usp = dest; count < len; count++)
	       {
		  if (*bp < 0)
		     (*range_error)++;
		  *usp++ = *bp++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
	       {
		  for (bp = (signed char *)src, lp = dest; count < len; count++)
		     *lp++ = *bp++;
		  break;
	       }
	       else
	       {
		  for (bp = (signed char *)src, ip = dest; count < len; count++)
		     *ip++ = *bp++;
		  break;
	       }
	    case NC_UINT:
	       for (bp = (signed char *)src, uip = dest; count < len; count++)
	       {
		  if (*bp < 0)
		     (*range_error)++;
		  *uip++ = *bp++;
	       }
	       break;
	    case NC_INT64:
	       for (bp = (signed char *)src, lip = dest; count < len; count++)
		  *lip++ = *bp++;
	       break;
	    case NC_UINT64:
	       for (bp = (signed char *)src, ulip = dest; count < len; count++)
	       {
		  if (*bp < 0)
		     (*range_error)++;
		  *ulip++ = *bp++;
	       }
	       break;
	    case NC_FLOAT:
	       for (bp = (signed char *)src, fp = dest; count < len; count++)
		  *fp++ = *bp++;
	       break;
	    case NC_DOUBLE:
	       for (bp = (signed char *)src, dp = dest; count < len; count++)
		  *dp++ = *bp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_UBYTE:
	 switch (dest_type)
	 {
	    case NC_BYTE:
	       for (ubp = (unsigned char *)src, bp = dest; count < len; count++)
	       {
		  if (!strict_nc3 && *ubp > X_SCHAR_MAX)
		     (*range_error)++;
		  *bp++ = *ubp++;
	       }
	       break;
	    case NC_SHORT:
	       for (ubp = (unsigned char *)src, sp = dest; count < len; count++)
		  *sp++ = *ubp++;
	       break;
	    case NC_UBYTE:
	       for (ubp = (unsigned char *)src, ubp1 = dest; count < len; count++)
		  *ubp1++ = *ubp++;
	       break;
	    case NC_USHORT:
	       for (ubp = (unsigned char *)src, usp = dest; count < len; count++)
		  *usp++ = *ubp++;
	       break;
	    case NC_INT:
	       if (dest_long)
	       {
		  for (ubp = (unsigned char *)src, lp = dest; count < len; count++)
		     *lp++ = *ubp++;
		  break;
	       }
	       else
	       {
		  for (ubp = (unsigned char *)src, ip = dest; count < len; count++)
		     *ip++ = *ubp++;
		  break;
	       }
	    case NC_UINT:
	       for (ubp = (unsigned char *)src, uip = dest; count < len; count++)
		  *uip++ = *ubp++;
	       break;
	    case NC_INT64:
	       for (ubp = (unsigned char *)src, lip = dest; count < len; count++)
		  *lip++ = *ubp++;
	       break;
	    case NC_UINT64:
	       for (ubp = (unsigned char *)src, ulip = dest; count < len; count++)
		  *ulip++ = *ubp++;
	       break;
	    case NC_FLOAT:
	       for (ubp = (unsigned char *)src, fp = dest; count < len; count++)
		  *fp++ = *ubp++;
	       break;
	    case NC_DOUBLE:
	       for (ubp = (unsigned char *)src, dp = dest; count < len; count++)
		  *dp++ = *ubp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_SHORT:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (sp = (short *)src, ubp = dest; count < len; count++)
	       {
		  if (*sp > X_UCHAR_MAX || *sp < 0)
		     (*range_error)++;
		  *ubp++ = *sp++;
	       }
	       break;
	    case NC_BYTE:
	       for (sp = (short *)src, bp = dest; count < len; count++)
	       {
		  if (*sp > X_SCHAR_MAX || *sp < X_SCHAR_MIN)
		     (*range_error)++;
		  *bp++ = *sp++;
	       }
	       break;
	    case NC_SHORT:
	       for (sp = (short *)src, sp1 = dest; count < len; count++)
		  *sp1++ = *sp++;
	       break;
	    case NC_USHORT:
	       for (sp = (short *)src, usp = dest; count < len; count++)
	       {
		  if (*sp > X_USHORT_MAX || *sp < 0)
		     (*range_error)++;
		  *usp++ = *sp++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (sp = (short *)src, lp = dest; count < len; count++)
		     *lp++ = *sp++;
	       else
		  for (sp = (short *)src, ip = dest; count < len; count++)
		     *ip++ = *sp++;
	       break;
	    case NC_UINT:
	       for (sp = (short *)src, uip = dest; count < len; count++)
		  *uip++ = *sp++;
	       break;
	    case NC_INT64:
	       for (sp = (short *)src, lip = dest; count < len; count++)
		  *lip++ = *sp++;
	       break;
	    case NC_UINT64:
	       for (sp = (short *)src, ulip = dest; count < len; count++)
		  *ulip++ = *sp++;
	       break;
	    case NC_FLOAT:
	       for (sp = (short *)src, fp = dest; count < len; count++)
		  *fp++ = *sp++;
	       break;
	    case NC_DOUBLE:
	       for (sp = (short *)src, dp = dest; count < len; count++)
		  *dp++ = *sp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_USHORT:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (usp = (unsigned short *)src, ubp = dest; count < len; count++)
	       {
		  if (*usp > X_UCHAR_MAX)
		     (*range_error)++;
		  *ubp++ = *usp++;
	       }
	       break;
	    case NC_BYTE:
	       for (usp = (unsigned short *)src, bp = dest; count < len; count++)
	       {
		  if (*usp > X_SCHAR_MAX)
		     (*range_error)++;
		  *bp++ = *usp++;
	       }
	       break;
	    case NC_SHORT:
	       for (usp = (unsigned short *)src, sp = dest; count < len; count++)
	       {
		  if (*usp > X_SHORT_MAX)
		     (*range_error)++;
		  *sp++ = *usp++;
	       }
	       break;
	    case NC_USHORT:
	       for (usp = (unsigned short *)src, usp1 = dest; count < len; count++)
		  *usp1++ = *usp++;
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (usp = (unsigned short *)src, lp = dest; count < len; count++)
		     *lp++ = *usp++;
	       else
		  for (usp = (unsigned short *)src, ip = dest; count < len; count++)
		     *ip++ = *usp++;
	       break;
	    case NC_UINT:
	       for (usp = (unsigned short *)src, uip = dest; count < len; count++)
		  *uip++ = *usp++;
	       break;
	    case NC_INT64:
	       for (usp = (unsigned short *)src, lip = dest; count < len; count++)
		  *lip++ = *usp++;
	       break;
	    case NC_UINT64:
	       for (usp = (unsigned short *)src, ulip = dest; count < len; count++)
		  *ulip++ = *usp++;
	       break;
	    case NC_FLOAT:
	       for (usp = (unsigned short *)src, fp = dest; count < len; count++)
		  *fp++ = *usp++;
	       break;
	    case NC_DOUBLE:
	       for (usp = (unsigned short *)src, dp = dest; count < len; count++)
		  *dp++ = *usp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_INT:
	 if (src_long)
	 {
	    switch (dest_type)
	    {
	       case NC_UBYTE:
		  for (lp = (long *)src, ubp = dest; count < len; count++)
		  {
		     if (*lp > X_UCHAR_MAX || *lp < 0)
			(*range_error)++;
		     *ubp++ = *lp++;
		  }
		  break;
	       case NC_BYTE:
		  for (lp = (long *)src, bp = dest; count < len; count++)
		  {
		     if (*lp > X_SCHAR_MAX || *lp < X_SCHAR_MIN)
			(*range_error)++;
		     *bp++ = *lp++;
		  }
		  break;
	       case NC_SHORT:
		  for (lp = (long *)src, sp = dest; count < len; count++)
		  {
		     if (*lp > X_SHORT_MAX || *lp < X_SHORT_MIN)
			(*range_error)++;
		     *sp++ = *lp++;
		  }
		  break;
	       case NC_USHORT:
		  for (lp = (long *)src, usp = dest; count < len; count++)
		  {
		     if (*lp > X_SHORT_MAX || *lp < X_SHORT_MIN)
			(*range_error)++;
		     *usp++ = *lp++;
		  }
		  break;
	       case NC_INT: /* src is long */
		  if (dest_long)
		  {
		     for (lp = (long *)src, lp1 = dest; count < len; count++)
		     {
			if (*lp > X_LONG_MAX || *lp < X_LONG_MIN)
			   (*range_error)++;
			*lp1++ = *lp++;
		     }
		  }
		  else /* dest is int */
		  {
		     for (lp = (long *)src, ip = dest; count < len; count++)
		     {
			if (*lp > X_INT_MAX || *lp < X_INT_MIN)
			   (*range_error)++;
			*ip++ = *lp++;
		     }
		  }
		  break;
	       case NC_UINT:
		  for (lp = (long *)src, uip = dest; count < len; count++)
		  {
		     if (*lp > X_UINT_MAX || *lp < 0)
			(*range_error)++;
		     *uip++ = *lp++;
		  }
		  break;
	       case NC_INT64:
		  for (lp = (long *)src, lip = dest; count < len; count++)
		     *lip++ = *lp++;
		  break;
	       case NC_UINT64:
		  for (lp = (long *)src, ulip = dest; count < len; count++)
		     *ulip++ = *lp++;
		  break;
	       case NC_FLOAT:
		  for (lp = (long *)src, fp = dest; count < len; count++)
		     *fp++ = *lp++;
		  break;
	       case NC_DOUBLE:
		  for (lp = (long *)src, dp = dest; count < len; count++)
		     *dp++ = *lp++;
		  break;
	       default:
		  LOG((0, "nc4_convert_type: unexpected dest type. "
		       "src_type %d, dest_type %d", src_type, dest_type));
		  return NC_EBADTYPE;
	    }
	 }
	 else
	 {
	    switch (dest_type)
	    {
	       case NC_UBYTE:
		  for (ip = (int *)src, ubp = dest; count < len; count++)
		  {
		     if (*ip > X_UCHAR_MAX || *ip < 0)
			(*range_error)++;
		     *ubp++ = *ip++;
		  }
		  break;
	       case NC_BYTE:
		  for (ip = (int *)src, bp = dest; count < len; count++)
		  {
		     if (*ip > X_SCHAR_MAX || *ip < X_SCHAR_MIN)
			(*range_error)++;
		     *bp++ = *ip++;
		  }
		  break;
	       case NC_SHORT:
		  for (ip = (int *)src, sp = dest; count < len; count++)
		  {
		     if (*ip > X_SHORT_MAX || *ip < X_SHORT_MIN)
			(*range_error)++;
		     *sp++ = *ip++;
		  }
		  break;
	       case NC_USHORT:
		  for (ip = (int *)src, usp = dest; count < len; count++)
		  {
		     if (*ip > X_SHORT_MAX || *ip < X_SHORT_MIN)
			(*range_error)++;
		     *usp++ = *ip++;
		  }
		  break;
	       case NC_INT: /* src is int */
		  if (dest_long)
		  {
		     for (ip = (int *)src, lp1 = dest; count < len; count++)
		     {
			if (*ip > X_LONG_MAX || *ip < X_LONG_MIN)
			   (*range_error)++;
			*lp1++ = *ip++;
		     }
		  }
		  else /* dest is int */
		  {
		     for (ip = (int *)src, ip1 = dest; count < len; count++)
		     {
			if (*ip > X_INT_MAX || *ip < X_INT_MIN)
			   (*range_error)++;
			*ip1++ = *ip++;
		     }
		  }
		  break;
	       case NC_UINT:
		  for (ip = (int *)src, uip = dest; count < len; count++)
		  {
		     if (*ip > X_UINT_MAX || *ip < 0)
			(*range_error)++;
		     *uip++ = *ip++;
		  }
		  break;
	       case NC_INT64:
		  for (ip = (int *)src, lip = dest; count < len; count++)
		     *lip++ = *ip++;
		  break;
	       case NC_UINT64:
		  for (ip = (int *)src, ulip = dest; count < len; count++)
		     *ulip++ = *ip++;
		  break;
	       case NC_FLOAT:
		  for (ip = (int *)src, fp = dest; count < len; count++)
		     *fp++ = *ip++;
		  break;
	       case NC_DOUBLE:
		  for (ip = (int *)src, dp = dest; count < len; count++)
		     *dp++ = *ip++;
		  break;
	       default:
		  LOG((0, "nc4_convert_type: unexpected dest type. "
		       "src_type %d, dest_type %d", src_type, dest_type));
		  return NC_EBADTYPE;
	    }
	 }
	 break;
      case NC_UINT:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (uip = (unsigned int *)src, ubp = dest; count < len; count++)
	       {
		  if (*uip > X_UCHAR_MAX)
		     (*range_error)++;
		  *ubp++ = *uip++;
	       }
	       break;
	    case NC_BYTE:
	       for (uip = (unsigned int *)src, bp = dest; count < len; count++)
	       {
		  if (*uip > X_SCHAR_MAX)
		     (*range_error)++;
		  *bp++ = *uip++;
	       }
	       break;
	    case NC_SHORT:
	       for (uip = (unsigned int *)src, sp = dest; count < len; count++)
	       {
		  if (*uip > X_SHORT_MAX)
		     (*range_error)++;
		  *sp++ = *uip++;
	       }
	       break;
	    case NC_USHORT:
	       for (uip = (unsigned int *)src, usp = dest; count < len; count++)
	       {
		  if (*uip > X_USHORT_MAX)
		     (*range_error)++;
		  *usp++ = *uip++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (uip = (unsigned int *)src, lp = dest; count < len; count++)
		  {
		     if (*uip > X_LONG_MAX)
			(*range_error)++;
		     *lp++ = *uip++;
		  }
	       else
		  for (uip = (unsigned int *)src, ip = dest; count < len; count++)
		  {
		     if (*uip > X_INT_MAX)
			(*range_error)++;
		     *ip++ = *uip++;
		  }
	       break;
	    case NC_UINT:
	       for (uip = (unsigned int *)src, uip1 = dest; count < len; count++)
	       {
		  if (*uip > X_UINT_MAX)
		     (*range_error)++;
		  *uip1++ = *uip++;
	       }
	       break;
	    case NC_INT64:
	       for (uip = (unsigned int *)src, lip = dest; count < len; count++)
		  *lip++ = *uip++;
	       break;
	    case NC_UINT64:
	       for (uip = (unsigned int *)src, ulip = dest; count < len; count++)
		  *ulip++ = *uip++;
	       break;
	    case NC_FLOAT:
	       for (uip = (unsigned int *)src, fp = dest; count < len; count++)
		  *fp++ = *uip++;
	       break;
	    case NC_DOUBLE:
	       for (uip = (unsigned int *)src, dp = dest; count < len; count++)
		  *dp++ = *uip++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_INT64:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (lip = (long long *)src, ubp = dest; count < len; count++)
	       {
		  if (*lip > X_UCHAR_MAX || *lip < 0)
		     (*range_error)++;
		  *ubp++ = *lip++;
	       }
	       break;
	    case NC_BYTE:
	       for (lip = (long long *)src, bp = dest; count < len; count++)
	       {
		  if (*lip > X_SCHAR_MAX || *lip < X_SCHAR_MIN)
		     (*range_error)++;
		  *bp++ = *lip++;
	       }
	       break;
	    case NC_SHORT:
	       for (lip = (long long *)src, sp = dest; count < len; count++)
	       {
		  if (*lip > X_SHORT_MAX || *lip < X_SHORT_MIN)
		     (*range_error)++;
		  *sp++ = *lip++;
	       }
	       break;
	    case NC_USHORT:
	       for (lip = (long long *)src, usp = dest; count < len; count++)
	       {
		  if (*lip > X_USHORT_MAX || *lip < 0)
		     (*range_error)++;
		  *usp++ = *lip++;
	       }
	       break;
	    case NC_UINT:
	       for (lip = (long long *)src, uip = dest; count < len; count++)
	       {
		  if (*lip > X_UINT_MAX || *lip < 0)
		     (*range_error)++;
		  *uip++ = *lip++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (lip = (long long *)src, lp = dest; count < len; count++)
		  {
		     if (*lip > X_LONG_MAX || *lip < X_LONG_MIN)
			(*range_error)++;
		     *lp++ = *lip++;
		  }
	       else
		  for (lip = (long long *)src, ip = dest; count < len; count++)
		  {
		     if (*lip > X_INT_MAX || *lip < X_INT_MIN)
			(*range_error)++;
		     *ip++ = *lip++;
		  }
	       break;
	    case NC_INT64:
	       for (lip = (long long *)src, lip1 = dest; count < len; count++)
	       {
		  if (*lip > X_INT64_MAX || *lip < X_INT64_MIN)
		     (*range_error)++;
		  *lip1++ = *lip++;
	       }
	       break;

	    case NC_UINT64:
	       for (lip = (long long *)src, ulip = dest; count < len; count++)
	       {
		  if (*lip < 0)
		     (*range_error)++;
		  *ulip++ = *lip++;
	       }
	       break;
	    case NC_FLOAT:
	       for (lip = (long long *)src, fp = dest; count < len; count++)
		  *fp++ = *lip++;
	       break;
	    case NC_DOUBLE:
	       for (lip = (long long *)src, dp = dest; count < len; count++)
		  *dp++ = *lip++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_UINT64:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (ulip = (unsigned long long *)src, ubp = dest; count < len; count++)
	       {
		  if (*ulip > X_UCHAR_MAX)
		     (*range_error)++;
		  *ubp++ = *ulip++;
	       }
	       break;
	    case NC_BYTE:
	       for (ulip = (unsigned long long *)src, bp = dest; count < len; count++)
	       {
		  if (*ulip > X_SCHAR_MAX)
		     (*range_error)++;
		  *bp++ = *ulip++;
	       }
	       break;
	    case NC_SHORT:
	       for (ulip = (unsigned long long *)src, sp = dest; count < len; count++)
	       {
		  if (*ulip > X_SHORT_MAX)
		     (*range_error)++;
		  *sp++ = *ulip++;
	       }
	       break;
	    case NC_USHORT:
	       for (ulip = (unsigned long long *)src, usp = dest; count < len; count++)
	       {
		  if (*ulip > X_USHORT_MAX)
		     (*range_error)++;
		  *usp++ = *ulip++;
	       }
	       break;
	    case NC_UINT:
	       for (ulip = (unsigned long long *)src, uip = dest; count < len; count++)
	       {
		  if (*ulip > X_UINT_MAX)
		     (*range_error)++;
		  *uip++ = *ulip++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (ulip = (unsigned long long *)src, lp = dest; count < len; count++)
		  {
		     if (*ulip > X_LONG_MAX)
			(*range_error)++;
		     *lp++ = *ulip++;
		  }
	       else
		  for (ulip = (unsigned long long *)src, ip = dest; count < len; count++)
		  {
		     if (*ulip > X_INT_MAX)
			(*range_error)++;
		     *ip++ = *ulip++;
		  }
	       break;
	    case NC_INT64:
	       for (ulip = (unsigned long long *)src, lip = dest; count < len; count++)
	       {
		  /*if (*ulip > X_INT64_MAX)
		    (*range_error)++;*/
		  *lip++ = *ulip++;
	       }
	       break;
	    case NC_UINT64:
	       for (ulip = (unsigned long long *)src, ulip1 = dest; count < len; count++)
	       {
		  if (*ulip > X_UINT64_MAX)
		     (*range_error)++;
		  *ulip1++ = *ulip++;
	       }
	       break;
	    case NC_FLOAT:
	       for (ulip = (unsigned long long *)src, fp = dest; count < len; count++)
		  *fp++ = *ulip++;
	       break;
	    case NC_DOUBLE:
	       for (ulip = (unsigned long long *)src, dp = dest; count < len; count++)
		  *dp++ = *ulip++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_FLOAT:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (fp = (float *)src, ubp = dest; count < len; count++)
	       {
		  if (*fp > X_UCHAR_MAX || *fp < 0)
		     (*range_error)++;
		  *ubp++ = *fp++;
	       }
	       break;
	    case NC_BYTE:
	       for (fp = (float *)src, bp = dest; count < len; count++)
	       {
		  if (*fp > (double)X_SCHAR_MAX || *fp < (double)X_SCHAR_MIN)
		     (*range_error)++;
		  *bp++ = *fp++;
	       }
	       break;
	    case NC_SHORT:
	       for (fp = (float *)src, sp = dest; count < len; count++)
	       {
		  if (*fp > (double)X_SHORT_MAX || *fp < (double)X_SHORT_MIN)
		     (*range_error)++;
		  *sp++ = *fp++;
	       }
	       break;
	    case NC_USHORT:
	       for (fp = (float *)src, usp = dest; count < len; count++)
	       {
		  if (*fp > X_SHORT_MAX || *fp < X_SHORT_MIN)
		     (*range_error)++;
		  *usp++ = *fp++;
	       }
	       break;
	    case NC_UINT:
	       for (fp = (float *)src, uip = dest; count < len; count++)
	       {
		  if (*fp > X_UINT_MAX || *fp < 0)
		     (*range_error)++;
		  *uip++ = *fp++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (fp = (float *)src, lp = dest; count < len; count++)
		  {
		     if (*fp > (double)X_LONG_MAX || *fp < (double)X_LONG_MIN)
			(*range_error)++;
		     *lp++ = *fp++;
		  }
	       else
		  for (fp = (float *)src, ip = dest; count < len; count++)
		  {
		     if (*fp > (double)X_INT_MAX || *fp < (double)X_INT_MIN)
			(*range_error)++;
		     *ip++ = *fp++;
		  }
	       break;
	    case NC_INT64:
	       for (fp = (float *)src, lip = dest; count < len; count++)
	       {
		  /*if (*fp > X_INT64_MAX)
		    (*range_error)++;*/
		  *lip++ = *fp++;
	       }
	       break;
	    case NC_UINT64:
	       for (fp = (float *)src, lip = dest; count < len; count++)
	       {
		  /*if (*fp > X_INT64_MAX)
		    (*range_error)++;*/
		  *lip++ = *fp++;
	       }
	       break;
	    case NC_FLOAT:
	       for (fp = (float *)src, fp1 = dest; count < len; count++)
	       {
/*		  if (*fp > X_FLOAT_MAX || *fp < X_FLOAT_MIN)
		  (*range_error)++;*/
		  *fp1++ = *fp++;
	       }
	       break;
	    case NC_DOUBLE:
	       for (fp = (float *)src, dp = dest; count < len; count++)
		  *dp++ = *fp++;
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      case NC_DOUBLE:
	 switch (dest_type)
	 {
	    case NC_UBYTE:
	       for (dp = (double *)src, ubp = dest; count < len; count++)
	       {
		  if (*dp > X_UCHAR_MAX || *dp < 0)
		     (*range_error)++;
		  *ubp++ = *dp++;
	       }
	       break;
	    case NC_BYTE:
	       for (dp = (double *)src, bp = dest; count < len; count++)
	       {
		  if (*dp > X_SCHAR_MAX || *dp < X_SCHAR_MIN)
		     (*range_error)++;
		  *bp++ = *dp++;
	       }
	       break;
	    case NC_SHORT:
	       for (dp = (double *)src, sp = dest; count < len; count++)
	       {
		  if (*dp > X_SHORT_MAX || *dp < X_SHORT_MIN)
		     (*range_error)++;
		  *sp++ = *dp++;
	       }
	       break;
	    case NC_USHORT:
	       for (dp = (double *)src, usp = dest; count < len; count++)
	       {
		  if (*dp > X_SHORT_MAX || *dp < X_SHORT_MIN)
		     (*range_error)++;
		  *usp++ = *dp++;
	       }
	       break;
	    case NC_UINT:
	       for (dp = (double *)src, uip = dest; count < len; count++)
	       {
		  if (*dp > X_UINT_MAX || *dp < 0)
		     (*range_error)++;
		  *uip++ = *dp++;
	       }
	       break;
	    case NC_INT:
	       if (dest_long)
		  for (dp = (double *)src, lp = dest; count < len; count++)
		  {
		     if (*dp > X_LONG_MAX || *dp < X_LONG_MIN)
			(*range_error)++;
		     *lp++ = *dp++;
		  }
	       else
		  for (dp = (double *)src, ip = dest; count < len; count++)
		  {
		     if (*dp > X_INT_MAX || *dp < X_INT_MIN)
			(*range_error)++;
		     *ip++ = *dp++;
		  }
	       break;
	    case NC_INT64:
	       for (dp = (double *)src, lip = dest; count < len; count++)
	       {
		  /*if (*dp > X_INT64_MAX)
		    (*range_error)++;*/
		  *lip++ = *dp++;
	       }
	       break;
	    case NC_UINT64:
	       for (dp = (double *)src, lip = dest; count < len; count++)
	       {
		  /*if (*dp > X_INT64_MAX)
		    (*range_error)++;*/
		  *lip++ = *dp++;
	       }
	       break;
	    case NC_FLOAT:
	       for (dp = (double *)src, fp = dest; count < len; count++)
	       {
		  if (*dp > X_FLOAT_MAX || *dp < X_FLOAT_MIN)
		     (*range_error)++;
		  *fp++ = *dp++;
	       }
	       break;
	    case NC_DOUBLE:
	       for (dp = (double *)src, dp1 = dest; count < len; count++)
	       {
		  if (*dp > X_DOUBLE_MAX || *dp < X_DOUBLE_MIN)
		     (*range_error)++;
		  *dp1++ = *dp++;
	       }
	       break;
	    default:
	       LOG((0, "nc4_convert_type: unexpected dest type. "
		    "src_type %d, dest_type %d", src_type, dest_type));
	       return NC_EBADTYPE;
	 }
	 break;
      default:
	 LOG((0, "nc4_convert_type: unexpected src type. "
	      "src_type %d, dest_type %d", src_type, dest_type));
	 return NC_EBADTYPE;
   }
   return NC_NOERR;
}

/* This function is called by nc4_rec_read_metadata when a dimension scale
 * dataset is encountered. It reads in the dimension data (creating a
 * new NC_DIM_INFO_T object), and also checks to see if this is a
 * dimension without a variable - that is, a coordinate dimension
 * which does not have any coordinate data. */
static int
read_scale(NC_GRP_INFO_T *grp, hid_t datasetid, char *obj_name, 
	   hsize_t scale_size, hsize_t max_scale_size, 
	   int *dim_without_var)
{
   char *start_of_len;
   char dimscale_name_att[NC_MAX_NAME + 1];
   int retval;

   /* Add a dimension for this scale. */
   if ((retval = nc4_dim_list_add(&grp->dim)))
      return retval;
   grp->dim->dimid = grp->file->nc4_info->next_dimid++;
   strncpy(grp->dim->name, obj_name, NC_MAX_NAME + 1);
   grp->dim->len = scale_size;
   grp->dim->hdf_dimscaleid = datasetid;

   /* If the dimscale has an unlimited dimension, then this dimension
    * is unlimited. */
   if (max_scale_size == H5S_UNLIMITED)
      grp->dim->unlimited++;

   /* If the scale name is set to DIM_WITHOUT_VARIABLE, then this is a
    * dimension, but not a variable. (If get_scale_name returns an
    * error, just move on, there's no NAME.) */
   if (H5DSget_scale_name(datasetid, dimscale_name_att, 
			  NC_MAX_NAME) >= 0)
   {
      if (!strncmp(dimscale_name_att, DIM_WITHOUT_VARIABLE, 
		   strlen(DIM_WITHOUT_VARIABLE)))
      {
	 if (grp->dim->unlimited)
	 {
	    size_t len = 0, *lenp = &len;
	    if ((retval = nc4_find_dim_len(grp, grp->dim->dimid, &lenp)))
	       return retval;
	    grp->dim->len = *lenp;
	 }
	 else
	 {
	    start_of_len = dimscale_name_att + strlen(DIM_WITHOUT_VARIABLE);
	    sscanf(start_of_len, "%d", &grp->dim->len);
	 }
	 (*dim_without_var)++;
      }
   }


   return NC_NOERR;
}

/* This function is called by read_dataset, (which is called by
 * nc4_rec_read_metadata) when a netCDF variable is found in the
 * file. This function reads in all the metadata about the var,
 * including the attributes. */
static int
read_var(NC_GRP_INFO_T *grp, hid_t datasetid, char *obj_name, 
	 size_t ndims, int is_scale, int num_scales)
{
   NC_VAR_INFO_T *var;
   int natts, a, d;

   NC_ATT_INFO_T *att;
   hid_t attid = 0;
   char att_name[NC_MAX_HDF5_NAME + 1];

#define CD_NELEMS 1
   H5Z_filter_t filter;
   int num_filters;
   unsigned int cd_values[CD_NELEMS];
   size_t cd_nelems = CD_NELEMS;
   hid_t propid = 0;
   size_t type_size;
   H5D_fill_value_t fill_status;
   H5T_order_t order;
   H5T_class_t type_class;
   H5D_layout_t layout;
   hsize_t chunksize[NC_MAX_DIMS];
   int retval = NC_NOERR;
   int f;

   assert(obj_name && grp);
   LOG((4, "read_var: obj_name %s", obj_name));

   /* Add a variable to the end of the group's var list. */
   if ((retval = nc4_var_list_add(&grp->var, &var)))
      return retval;
	    
   /* Fill in what we already know. */
   var->hdf_datasetid = datasetid;
   var->varid = grp->nvars++;
   var->created++;
   strcpy(var->name, obj_name);
   var->ndims = ndims;

   /* Find out what filters are applied to this HDF5 dataset,
    * fletcher32, deflate, and/or shuffle. All other filters are
    * ignored. */
   if ((propid = H5Dget_create_plist(datasetid)) < 0) 
      BAIL(NC_EHDFERR);

   /* Get the chunking info for non-scalar vars. */
   if ((layout = H5Pget_layout(propid)) < -1)
      BAIL(NC_EHDFERR);
   if (layout == H5D_CHUNKED)
   {
      if (H5Pget_chunk(propid, NC_MAX_DIMS, chunksize) < 0)
	 BAIL(NC_EHDFERR);
      for (d = 0; d < var->ndims; d++)
	 var->chunksizes[d] = chunksize[d];
   }
   else if (layout == H5D_CONTIGUOUS)
      var->contiguous++;

   /* The possible values of filter (which is just an int) can be
    * found in H5Zpublic.h. */
   if ((num_filters = H5Pget_nfilters(propid)) < 0) 
      BAIL(NC_EHDFERR);
   for (f = 0; f < num_filters; f++)
   {
      if ((filter = H5Pget_filter2(propid, f, NULL, &cd_nelems, 
				   cd_values, 0, NULL, NULL)) < 0)
	 BAIL(NC_EHDFERR);
      switch (filter)
      {
	 case H5Z_FILTER_SHUFFLE:
	    var->shuffle = 1;
	    break;
	 case H5Z_FILTER_FLETCHER32:
	    var->fletcher32 = 1;
	    break;
	 case H5Z_FILTER_DEFLATE:
	    var->deflate++;
	    if (cd_nelems != CD_NELEMS ||
		cd_values[0] < MIN_DEFLATE_LEVEL ||
		cd_values[0] > MAX_DEFLATE_LEVEL)
	       BAIL(NC_EHDFERR);
	    var->deflate_level = cd_values[0];
	    break;
	 default:
	    LOG((1, "Yikes! Unknown filter type found on dataset!"));
	    break;
      }
   }
	       
   /* Get the HDF5 type - we'll need it later. */
   if ((var->hdf_typeid = H5Dget_type(datasetid)) < 0)
      BAIL(NC_EHDFERR);

   /* While we have the typeid handy, what is the endianness of this
    * type? */
   if ((type_class = H5Tget_class(var->hdf_typeid)) < 0)
      BAIL(NC_EHDFERR);
   if (type_class == H5T_INTEGER)
   {
      if ((order = H5Tget_order(var->hdf_typeid)) < 0) 
	 BAIL(NC_EHDFERR);
      if (order == H5T_ORDER_LE)
	 var->endianness = NC_ENDIAN_LITTLE;
      else if (order == H5T_ORDER_BE)
	 var->endianness = NC_ENDIAN_BIG;
   }

   /* Is there a fill value associated with this dataset? */
   if (H5Pfill_value_defined(propid, &fill_status) < 0)
      BAIL(NC_EHDFERR);

   /* Get the fill value, if there is one defined. */
   if (fill_status == H5D_FILL_VALUE_USER_DEFINED)
   {
      hid_t native_typeid;
      /* Allocate space to hold the fill value. */
      if ((native_typeid = H5Tget_native_type(var->hdf_typeid, H5T_DIR_DEFAULT)) < 0) 
	 return NC_EHDFERR;
      if (!(type_size = H5Tget_size(native_typeid)))
	 return NC_EHDFERR;
      if (!var->fill_value)
	 if (!(var->fill_value = nc_malloc(type_size)))
	    BAIL(NC_ENOMEM);
      
      /* Get the fill value from the HDF5 property lust. */
      if (H5Pget_fill_value(propid, native_typeid, var->fill_value) < 0)
	 BAIL(NC_EHDFERR);
   }
   else
      var->no_fill = 1;

   /* If it's a scale, mark it as such. If not, allocate space to
    * remember whether the dimscale has been attached for each
    * dimension. */

   if (is_scale)
   {
      var->dimscale++;
      var->dimids[0] = grp->dim->dimid;
   }
   else
      if (ndims && !(var->dimscale_attached = nc_calloc(ndims, sizeof(int))))
	 BAIL(NC_ENOMEM);	
       
   /* If this is not a scale, and has scales, iterate
    * through them. (i.e. this is a variable that is not a
    * coordinate variable) */
   if (!is_scale && num_scales)
   {
      /* Store id information allowing us to match hdf5
       * dimscales to netcdf dimensions. */
      if (!(var->dimscale_hdf5_objids = nc_malloc(ndims * sizeof(struct hdf5_objid))))
	 BAIL(NC_ENOMEM);
      for (d = 0; d < var->ndims; d++)
      {
	 LOG((5, "read_var: about to iterate over scales for dim %d", d));
	 if (H5DSiterate_scales(var->hdf_datasetid, d, NULL, dimscale_visitor,
				&(var->dimscale_hdf5_objids[d])) < 0)
	    BAIL(NC_EHDFERR);
/*	 LOG((5, "read_var: collected scale info for dim %d "
	 "var %s fileno[0] %d objno[0] %d fileno[1] %d objno[1] %d", 
	 d, var->name, var->dimscale_hdf5_objids[d].fileno[0], 
	 var->dimscale_hdf5_objids[d].objno[0], 
	 var->dimscale_hdf5_objids[d].fileno[1], 
	 var->dimscale_hdf5_objids[d].objno[1]));*/
	 var->dimscale_attached[d]++;
      }
   }
	
   /* Now read all the attributes of this variable, ignoring the
      ones that hold HDF5 dimension scale information. */
   if ((natts = H5Aget_num_attrs(datasetid)) < 0)
      BAIL(NC_EATTMETA);
   for (a = 0; a<natts; a++)
   {
      /* Close the attribute and try to move on with our
       * lives. Like bits through the network port, so
       * flows the Days of Our Lives! */
      if (attid && H5Aclose(attid) < 0)
	 BAIL(NC_EHDFERR);

      /* Open the att and get its name. */
      if ((attid = H5Aopen_idx(datasetid, (unsigned int)a)) < 0)
	 BAIL(NC_EATTMETA);
      if (H5Aget_name(attid, NC_MAX_HDF5_NAME, att_name) < 0)
	 BAIL(NC_EATTMETA);
      LOG((4, "read_var: a %d att_name %s", a, att_name));

      /* Should we ignore this attribute? */	
      if (strcmp(att_name, REFERENCE_LIST) &&
	  strcmp(att_name, CLASS) &&
	  strcmp(att_name, DIMENSION_LIST) &&
	  strcmp(att_name, NAME))
      {
	 /* Add to the end of the list of atts for this var. */
	 if ((retval = nc4_att_list_add(&var->att)))
	    BAIL(retval);
	 for (att = var->att; att->next; att = att->next)
	    ;
		     
	 /* Fill in the information we know. */
	 att->attnum = var->natts++;
	 strcpy(att->name, att_name);
		     
	 /* Read the rest of the info about the att,
	  * including its values. */
	 if ((retval = pg_att_grpa(GET, grp, var->varid, att)))
	    BAIL(retval);

	 att->created++;
      } /* endif not HDF5 att */
   } /* next attribute */

  exit:
   if (propid > 0 && H5Pclose(propid) < 0)
      BAIL2(NC_EHDFERR);
   if (attid > 0 && H5Aclose(attid) < 0)
      BAIL2(NC_EHDFERR);
   return retval;
}

/* This function is called by nc4_rec_read_metadata to read all the group
 * level attributes (i.e. the NC_GLOBAL atts for this group. */
static int
read_grp_atts(NC_GRP_INFO_T *grp)
{
   hid_t attid = 0;
   hsize_t num_obj, i;
   NC_ATT_INFO_T *att;
   NC_TYPE_INFO_T *type;
   char obj_name[NC_MAX_HDF5_NAME + 1];
   int retval = NC_NOERR;

   num_obj = H5Aget_num_attrs(grp->hdf_grpid);
   for (i = 0; i < num_obj; i++)
   {
      if (attid > 0) 
	 H5Aclose(attid);
      if ((attid = H5Aopen_idx(grp->hdf_grpid, (unsigned int)i)) < 0)
	 BAIL(NC_EATTMETA);
      if (H5Aget_name(attid, NC_MAX_NAME + 1, obj_name) < 0)
	 BAIL(NC_EATTMETA);
      LOG((4, "reading attribute of _netCDF group, named %s", obj_name));

      /* This may be an attribute telling us that strict netcdf-3
       * rules are in effect. If so, we will make note of the fact,
       * but not add this attribute to the metadata. It's not a user
       * attribute, but an internal netcdf-4 one. */
      if (!strcmp(obj_name, NC3_STRICT_ATT_NAME))
	 grp->file->nc4_info->cmode |= NC_CLASSIC_MODEL;
      else
      {
	 /* Add an att struct at the end of the list, and then go to it. */
	 if ((retval = nc4_att_list_add(&grp->att)))
	    BAIL(retval);
	 for (att = grp->att; att->next; att = att->next)
	    ;
	 strncpy(att->name, obj_name, NC_MAX_NAME + 1);
	 att->name[NC_MAX_NAME] = 0;
	 att->attnum = grp->natts++;
	 if ((retval = pg_att_grpa(GET, grp, NC_GLOBAL, att)))
	    BAIL(retval);
	 att->created++;
	 if ((retval = nc4_find_type(grp->file->nc4_info, att->xtype, &type)))
	    BAIL(retval);
	 if (type)
	    att->class = type->class;
      }
   }

  exit:
   if (attid > 0 && H5Aclose(attid) < 0)
      BAIL2(NC_EHDFERR);
   return retval;
}

/* This function is called when nc4_rec_read_metadata encounters an HDF5
 * dataset when reading a file. */
static int
read_dataset(NC_GRP_INFO_T *grp, char *obj_name)
{
   hid_t datasetid = 0;   
   hid_t spaceid = 0;
   size_t ndims;
   hsize_t dims[NC_MAX_DIMS], max_dims[NC_MAX_DIMS];
   int is_scale = 0;
   int dim_without_var = 0;
   int num_scales = 0;		  
   int retval = NC_NOERR;

   /* Open this dataset. */
   if ((datasetid = H5Dopen(grp->hdf_grpid, obj_name)) < 0)
      BAIL(NC_EVARMETA);

   /* Get the dimension information for this dataset. */
   if ((spaceid = H5Dget_space(datasetid)) < 0)
      BAIL(NC_EHDFERR);
   if ((ndims = H5Sget_simple_extent_ndims(spaceid)) < 0)
      BAIL(NC_EHDFERR);
   if (ndims > NC_MAX_DIMS)
      BAIL(NC_EMAXDIMS);
   if (H5Sget_simple_extent_dims(spaceid, dims, max_dims) < 0)
      BAIL(NC_EHDFERR);

   /* Is this a dimscale? */
   if ((is_scale = H5DSis_scale(datasetid)) < 0)
      BAIL(NC_EHDFERR);
   if (is_scale)
   {
      /* For netCDF-4, this better have only one dimension! */
      if (ndims != 1)
	 BAIL(NC_EDIMMETA);

      /* Read the scale information. */
      if ((retval = read_scale(grp, datasetid, obj_name, dims[0], 
			       max_dims[0], &dim_without_var)))
	 BAIL(retval);
   }
   else
   {
      /* Find out how many scales are attached to this
       * dataset. H5DSget_num_scales returns an error if there are no
       * scales, so convert a negative return value to zero. */
      num_scales = H5DSget_num_scales(datasetid, 0);
      if (num_scales < 0)
	 num_scales = 0;
   }

   /* Add a var to the linked list, and get it's metadata,
    * unless this is one of those funny dimscales that are a
    * dimension in netCDF but not a variable. (Spooky!) */
   if (!dim_without_var)
      if ((retval = read_var(grp, datasetid, obj_name, ndims, 
			     is_scale, num_scales)))
	 BAIL(retval);
   
   return NC_NOERR;

  exit:
   if (datasetid && H5Dclose(datasetid) < 0)
      BAIL2(retval);
   if (spaceid && H5Sclose(spaceid) <0)
      BAIL2(retval);
   return retval;
}

/* This function recursively reads all the metadata in a HDF5 group,
   and creates and fill in the netCDF-4 global metadata structure. */
int
nc4_rec_read_metadata(NC_GRP_INFO_T *grp)
{
   hsize_t num_obj, i;
   int obj_class;
   char obj_name[NC_MAX_HDF5_NAME + 1];
   NC_HDF5_FILE_INFO_T *h5 = grp->file->nc4_info;
   NC_GRP_INFO_T *child_grp;
   int retval = NC_NOERR;
   H5O_info_t obj_info;
   size_t size;

   assert(grp && grp->name);
   LOG((3, "nc4_rec_read_metadata: grp->name %s", grp->name));

   /* Open this HDF5 group and retain it's grpid. It will remain open
    * with HDF5 until this file is nc_closed. */
   if (!grp->hdf_grpid)
   {
      if (grp->parent)
      {
   	 if ((grp->hdf_grpid = H5Gopen2(grp->parent->hdf_grpid, grp->name, H5P_DEFAULT)) < 0)
	    return NC_EHDFERR;
      }
      else
      {
	 if ((grp->hdf_grpid = H5Gopen2(grp->file->nc4_info->hdfid, "/", H5P_DEFAULT)) < 0)
	    return NC_EHDFERR;
      }
   }
   assert(grp->hdf_grpid > 0);

   /* Find the variables. Read their metadata and attributes. */
   if (H5Gget_num_objs(grp->hdf_grpid, &num_obj) < 0)
      BAIL(NC_EVARMETA);
   for (i = 0; i < num_obj; i++)
   {
      if (H5Oget_info_by_idx(grp->hdf_grpid, ".", H5_INDEX_CRT_ORDER, H5_ITER_INC, 
			     i, &obj_info, H5P_DEFAULT) < 0) 
	 BAIL(NC_EHDFERR);
      obj_class = obj_info.type;
      if ((size = H5Lget_name_by_idx(grp->hdf_grpid, ".", H5_INDEX_CRT_ORDER, H5_ITER_INC, i,
				     NULL, 0, H5P_DEFAULT)) < 0) 
	 BAIL(NC_EHDFERR);
      if (size > NC_MAX_NAME)
	 BAIL(NC_EMAXNAME);
      if (H5Lget_name_by_idx(grp->hdf_grpid, ".", H5_INDEX_CRT_ORDER, H5_ITER_INC, i,
			     obj_name, size+1, H5P_DEFAULT) < 0) 
	 BAIL(NC_EHDFERR);
      LOG((4, "nc4_rec_read_metadata: encountered HDF5 object obj_class %d obj_name %s", 
	   obj_class, obj_name));
      /* Deal with groups and datasets. */
      switch(obj_class)
      {
	 case H5O_TYPE_GROUP:
	    /* Add group object to this groups children. */
	    if ((retval = nc4_grp_list_add(&(grp->children), h5->next_nc_grpid++, 
					   grp, grp->file, obj_name, &child_grp)))
	       BAIL(retval);
	    
	    /* Recursively read the child group's metadata. */
	    if ((retval =  nc4_rec_read_metadata(child_grp)))
	       BAIL(retval);

	    break;
	 case H5O_TYPE_DATASET:
	    /* Learn all about this dataset, which may be a dimscale
	     * (i.e. dimension metadata), or real data. */
	    if ((retval = read_dataset(grp, obj_name)))
	       BAIL(retval);

	    break;
	 case H5O_TYPE_NAMED_DATATYPE:
	    /* Learn about the user-defined type. */
	    if ((retval = read_type(grp, obj_name)))
	       BAIL(retval);

	    break;
	 case H5G_LINK:
	    /* Since I don't know what to do with linkes, I'll just
	     * ignore them. */
	    LOG((4, "This is a link object. Have a nice day."));

	    break;
	 default:
	    LOG((0, "Unknown object class %d in nc4_rec_read_metadata!", 
		 obj_class));
      }
   }

   /* Scan the group for global (i.e. group-level) attributes. */
   if ((retval = read_grp_atts(grp)))
      BAIL(retval);

   return NC_NOERR; /* everything worked! */

  exit: 
   /* If we get here, there was an error. Close all HDF5objects that were
    * open by this function. */
   if (grp->hdf_grpid && H5Gclose(grp->hdf_grpid) < 0)
      BAIL2(NC_EHDFERR);
   return retval;
}

/* In our first pass through the data, we may have encountered
 * variables before encountering the compound types that are needed to
 * understand them, so go through the vars in this file and make sure
 * we've got a valid type for each. */
int
nc4_rec_match_types(NC_GRP_INFO_T *grp)
{
   NC_HDF5_FILE_INFO_T *h5 = grp->file->nc4_info;
   NC_GRP_INFO_T *g;
   NC_VAR_INFO_T *var;
   NC_ATT_INFO_T *att;
   NC_TYPE_INFO_T *type;
   NC_FIELD_INFO_T *field;
   int retval = NC_NOERR;

   assert(grp && grp->name);
   LOG((4, "nc4_rec_match_types: grp->name %s", grp->name));

   /* Perform var type match for child groups. */
   for (g = grp->children; g; g = g->next)
      if ((retval = nc4_rec_match_types(g)))
	 return retval;
   
   /* Check all the field types in all user-defined types in this
    * group. */
   for (type = grp->type; type; type = type->next)
   {
      if (type->class == NC_COMPOUND)
      {
	 for (field = type->field; field; field = field->next)
	    if (field->nctype == NC_NAT)
	    {
	       LOG((5, "field %s has no netcdf type - finding one...", field->name));
	       if((retval = get_netcdf_type(h5, field->hdf_typeid, &(field->nctype))))
		  return retval;
	       LOG((5, "nc_type for this field is %d", field->nctype));
	    }
      }
      else if (type->class == NC_VLEN)
      {
	 if (type->base_nc_type == NC_NAT)
	 {
	    LOG((5, "VLEN has no base netcdf type - finding one..."));
	    if((retval = get_netcdf_type(h5, type->base_hdf_typeid, &(type->base_nc_type))))
	       return retval;
	    LOG((5, "base type for this vlen is %d", type->base_nc_type));
	 }
      }
   }
   
   /* Check all the vars in this group. */
   for (var = grp->var; var; var = var->next)
   {
      /* Look up netCDF types for all the vars that don't know their
       * types. */
      if (var->xtype == NC_NAT)
      {
	 LOG((5, "var %s has no netcdf type - finding one...", var->name));
	 if((retval = get_netcdf_type(h5, var->hdf_typeid, &(var->xtype))))
	    return retval;
	 LOG((5, "nc_type for this var is %d", var->xtype));
      }

      /* Check the types of all atts for this var. */
      for (att = var->att; att; att = att->next)
      {
	 if (att->xtype == NC_NAT)
	 {
	    LOG((5, "att %s has no netcdf type - finding one...", att->name));
	    if((retval = get_netcdf_type(h5, att->hdf_typeid, &(att->xtype))))
	       return retval;
	    LOG((5, "nc_type for this att is %d", att->xtype));
	 }
      }
   }

   /* Check the types of all atts for this group. */
   for (att = grp->att; att; att = att->next)
   {
      if (att->xtype == NC_NAT)
      {
	 LOG((5, "att %s has no netcdf type - finding one...", att->name));
	 if((retval = get_netcdf_type(h5, att->hdf_typeid, &(att->xtype))))
	    return retval;
	 LOG((5, "nc_type for this att is %d", att->xtype));
      }
   }

   return retval;
}

/* In our first pass through the data, we may have encountered
 * variables before encountering their dimscales, so go through the
 * vars in this file and make sure we've got a dimid for each. */
int
nc4_rec_match_dimscales(NC_GRP_INFO_T *grp)
{
   NC_GRP_INFO_T *g;
   NC_VAR_INFO_T *var;
   NC_DIM_INFO_T *dim;
   H5G_stat_t statbuf;
   int d, finished;
   int retval = NC_NOERR;

   assert(grp && grp->name);
   LOG((4, "nc4_rec_match_dimscales: grp->name %s", grp->name));

   /* Perform var dimscale match for child groups. */
   for (g = grp->children; g; g = g->next)
      if ((retval = nc4_rec_match_dimscales(g)))
	 return retval;
   
   /* Check all the vars in this group. If they have dimscale info,
    * try and find a dimension for them. */
   for (var = grp->var; var; var = var->next)
   {
      if (var->dimscale_hdf5_objids)
      {
	 for (d = 0; d < var->ndims; d++)
	 {
	    LOG((5, "nc4_rec_match_dimscales: var %s has dimscale info...", var->name));
	    /* Look at all the dims in this group to see if they
	     * match. */
	    finished = 0;
	    for (g = grp; g && !finished; g = g->parent)
	    {
	       for (dim = g->dim; dim; dim = dim->next)
	       {
		  if (!dim->hdf_dimscaleid)
		     return NC_EDIMMETA;
		  if (H5Gget_objinfo(dim->hdf_dimscaleid, ".", 1, &statbuf) < 0)
		     return NC_EHDFERR;
		  if (var->dimscale_hdf5_objids[d].fileno[0] == statbuf.fileno[0] && 
		      var->dimscale_hdf5_objids[d].objno[0] == statbuf.objno[0] &&
		      var->dimscale_hdf5_objids[d].fileno[1] == statbuf.fileno[1] && 
		      var->dimscale_hdf5_objids[d].objno[1] == statbuf.objno[1])
		  {
		     LOG((4, "nc4_rec_match_dimscales: for dimension %d, found dim %s", 
			  d, dim->name));
		     var->dimids[d] = dim->dimid;
		     finished++;
		     break;
		  }
	       } /* next dim */
	    } /* next grp */
	    LOG((5, "nc4_rec_match_dimscales: dimid for this dimscale is %d", var->xtype));
	 } /* next var->dim */
      }
   }

   return retval;
}

/* Get the length, in bytes, of one element of a type in memory. */
int 
nc4_get_typelen_mem(NC_HDF5_FILE_INFO_T *h5, nc_type xtype, int is_long, 
		    size_t *len)
{
   NC_TYPE_INFO_T *type;
   int retval;

   LOG((4, "nc4_get_typelen_mem xtype: %d", xtype));
   assert(len);

   /* If this is an atomic type, the answer is easy. */
   switch (xtype)
   {
      case NC_BYTE:
      case NC_CHAR:
      case NC_UBYTE:
	 *len = sizeof(char);
	 return NC_NOERR;
      case NC_SHORT:
      case NC_USHORT:
	 *len = sizeof(short);
	 return NC_NOERR;
      case NC_INT:
      case NC_UINT:
	 if (is_long)
	    *len = sizeof(long);
	 else
	    *len = sizeof(int);
	 return NC_NOERR;
      case NC_FLOAT:
	 *len = sizeof(float);
	 return NC_NOERR;
      case NC_DOUBLE:
	 *len = sizeof(double);
	 return NC_NOERR;
      case NC_INT64:
      case NC_UINT64:
	 *len = sizeof(long long);
	 return NC_NOERR;
      case NC_STRING:
	 *len = 0; /* can't even guess! */
	 return NC_NOERR;
   }

   /* See if var is compound type. */
   if ((retval = nc4_find_type(h5, xtype, &type)))
      return retval;

   if (!type)
      return NC_EBADTYPE;

   *len = type->size;

   LOG((5, "type->size ", type->size));

   return NC_NOERR;
}
