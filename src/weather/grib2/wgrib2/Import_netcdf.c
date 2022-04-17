/*
 * Import_netcdf.c  2017  Public Domain, Wesley Ebisuzaki
 *
 * This option opens a netcdf file (3 or 4 depending on netcdf libraries),
 * reads a hyperslab, and closes the netcdf file.
 *
 * The routine could be made faster by only opening the netcdf file once.
 * You could do this by adding a routine like ffopen and ffclose which
 * would keep a history of opened files and associated ncids.
 *
 * If I did a lot of netcdf -> grib conversions, I would do a before b.
 *  a) a netcdf <-> grib time conversions
 *  b) minimizing opens/closes of netcdf files
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "grb2.h"
#include "wgrib2.h"
#include "fnlist.h"

/*
 * Import_netcdf.c  2017  Public Domain, Wesley Ebisuzaki
 *
 * This option opens a netcdf file (3 or 4 depending on netcdf libraries),
 * reads a hyperslab, and closes the netcdf file.
 *
 * The routine could be made faster by only opening the netcdf file once.
 * You could do this by adding a routine like ffopen and ffclose which
 * would keep a history of opened files and associated ncids.
 *
 * If I did a lot of netcdf -> grib conversions, I would do a before b.
 *  a) a netcdf <-> grib time conversions
 *  b) minimizing opens/closes of netcdf files
 *
 */


#if defined USE_NETCDF3 || defined USE_NETCDF4

#include <netcdf.h>

extern int decode;
extern int use_scale;

/*
 * HEADER:100:import_netcdf:misc:3:TESTING X=file Y=var Z=hyper-cube specification
 */

int f_import_netcdf(ARG3) {
    int status, ncid, ndims, nvars, ngatts, unlimdimid;
    int var_id, var_ndims, var_dimids[NC_MAX_VAR_DIMS], var_natts;
    nc_type var_type;
    size_t recs;
    size_t count[NC_MAX_VAR_DIMS], start[NC_MAX_VAR_DIMS];
    char name[NC_MAX_NAME+1];
    char attr[81];
    int i, j, k, m;
    unsigned int c0, s0, npnts0;
    int has_FillValue, has_missing_value;
    double FillValue, missing_value, limits;
    nc_type fv_type, nctype;
    size_t fv_len, lenp;
    double scale_factor, add_offset, *ddata;

    if (mode == -1) {
	decode = 1;
    }
    if (mode >= 0) {
fprintf(stderr,">>netcdf0: ndata=%d\n", (int) ndata);
	// open netcdf file
        status = nc_open(arg1, NC_NOWRITE, &ncid);
        if (status != NC_NOERR) fatal_error("import_netcdf: nc_open file %s", arg1);

	// get number of variables etc
        status = nc_inq(ncid, &ndims, &nvars, &ngatts, &unlimdimid);
        if (status != NC_NOERR) fatal_error_i("import_netcdf: nc_inq %d error", status);
//        fprintf(stderr,"ndimsp=%d nvarsp=%d nattsp=%d, unlim=%d\n", ndims, nvars, ngatts, unlimdimid);

	// get variable id
        status = nc_inq_varid(ncid, arg2, &var_id);
        if (status != NC_NOERR) {
	    fprintf(stderr,"import_netcdf: %s is not valid variable, valid variables are\n", arg2);
	    for (i = 0; i < nvars; i++) {
		status = nc_inq_varname(ncid, i, name);
                if (status == NC_NOERR) fprintf(stderr,"variable %d: %s\n",i,name);
	    }
	    fatal_error_i("import_netcdf: nc_inq_varid %d error", status);
	}

	/* get particulars about variable */
	status = nc_inq_var(ncid, var_id, 0, &var_type, &var_ndims, var_dimids, &var_natts);
        if (status != NC_NOERR) fatal_error_i("import_netcdf: nc_inq_var %d error", status);
        fprintf(stderr,"ndims=%d var_type=%d #var_attributes %d\n", var_ndims, var_type, var_natts);

	for (i = 0; i < var_natts; i++) {
	    status = nc_inq_attname(ncid, var_id, i, name);
            if (status != NC_NOERR) fatal_error("import_netcdf: nc_inq_attname","");
	    status = nc_inq_att(ncid, var_id, name, &nctype, &lenp);
            if (status != NC_NOERR) fatal_error("import_netcdf: nc_inq_att","");

	    if (nctype == NC_CHAR && lenp <= sizeof(attr)-1) {
		status = nc_get_att_text(ncid,var_id,name,attr);
		attr[lenp] = 0;
	        fprintf(stderr,"%s.%d attr=%s: %s\n", arg2, i, name, attr);
	    }
	    else {
	        fprintf(stderr,"%s.%d attr=%s type=%d len=%d\n", arg2, i, name, nctype, (int) lenp);
	    }
	}

	// get the _FillValue
	has_FillValue = 0;
	FillValue = 0.0;
	status = nc_inq_att(ncid, var_id, "_FillValue", &fv_type, &fv_len);
	if (status == NC_NOERR && fv_len == 1) {
	    status = nc_get_att_double(ncid, var_id, "_FillValue", &FillValue);
            if (status == NC_NOERR) has_FillValue = 1;
	}

	// get the missing_value (assume scalar, not vector)
	has_missing_value = 0;
	missing_value = 0.0;
	status = nc_inq_att(ncid, var_id, "missing_value", &fv_type, &fv_len);
	if (status == NC_NOERR && fv_len == 1) {
	    status = nc_get_att_double(ncid, var_id, "missing_value", &missing_value);
            if (status == NC_NOERR) has_missing_value = 1;
	}
	fprintf(stderr,"_FillValue=%lf %d missing_value=%lf %d\n", FillValue,has_FillValue, missing_value,has_missing_value);

	// get scale_factor (if present)
	scale_factor = 1.0;
	status = nc_inq_att(ncid, var_id, "scale_factor", &fv_type, &fv_len);
	if (status == NC_NOERR && fv_len == 1) {
	    status = nc_get_att_double(ncid, var_id, "scale_factor", &scale_factor);
            if (status != NC_NOERR) fatal_error("import_netcdf: nc_get_att_double scale_factor","");
	}

	// get add_offset (if present)
	add_offset = 0.0;
	status = nc_inq_att(ncid, var_id, "add_offset", &fv_type, &fv_len);
	if (status == NC_NOERR && fv_len == 1) {
	    status = nc_get_att_double(ncid, var_id, "add_offset", &add_offset);
            if (status != NC_NOERR) fatal_error("import_netcdf: nc_get_att_double add_offset","");
	}
	fprintf(stderr,"import_netcdf scale_factor %lf, add_offset=%lf\n", scale_factor, add_offset);

	/* parse arg3, hypercube definition,  start1:count1:start2:count2:..:startN:countN */
	i = 0;
	k = sscanf(arg3,"%u:%u%n", &s0, &c0, &m);
	while (k == 2) {
	    start[i] = s0;
	    count[i] = c0;
	    i++;
	    arg3 += m + 1;
	    k = sscanf(arg3,"%u:%u%n", &s0, &c0, &m);
	}

	if (i != var_ndims) {
	    fprintf(stderr,"dimension mismatch %s, netcdf file has\n", arg3);
	    for (i = 0; i < var_ndims; i++) {
	        status = nc_inq_dim(ncid, var_dimids[i], name, &recs);
	        fprintf(stderr,"   dim %d id=%d name=%s recs=%d\n", i, var_dimids[i], name, (int) (int) recs);
	    }
	    fatal_error("import_netcdf: dimensions do not match","");
	}

        npnts0 = 1;
	for (j = 0; j < var_ndims; j++) {
	    status = nc_inq_dim(ncid, var_dimids[j], name, &recs);
            if (status != NC_NOERR) fatal_error_i("import_netcdf:nc_inq_dim %d", status);
	    if (count[j] != 1 && count[j] != recs) {
	        fatal_error_ii("import_netcdf: size dimension %d size=%d",j, (int) recs);
	    }
	    npnts0 *= count[j];
	}
	if (npnts0 > ndata) fatal_error_ii("import_netcdf: size mismatch grib:%u netcdf:%u",ndata,npnts0);
	if (npnts0 < ndata) fprintf(stderr,"WARNING: import_netcdf: size mismatch grib:%u netcdf:%u\ndata is padded\n", ndata, npnts0);

	/* read the data */
	ddata = (double *) malloc(sizeof(double) * (size_t) ndata);
        if (ddata == NULL) fatal_error("import_netcdf: memory allocation","");

fprintf(stderr,">>netcdf: ndata=%d ", (int) ndata);
for (j = 0; j < var_ndims; j++) fprintf(stderr, " s=%d c=%d ", (int) start[j], (int) count[j]);
fprintf(stderr,"\n");

	status = nc_get_vara_double(ncid, var_id, start, count, &(ddata[0]));

        if (status != NC_NOERR) fatal_error_i("import_netcdf: nc_get_vara_double rc=%d",status);

#pragma omp parallel private(i)
	{
	    if (has_FillValue) {
	       limits = 0.01 * fabs(FillValue);
#pragma omp for
	        for (i = 0; i < ndata; i++) {
		    if (fabs(ddata[i] - FillValue) < limits) ddata[i] = UNDEFINED;
	        }
	    }
	    if (has_missing_value) {
	        limits = 0.01 * fabs(missing_value);
#pragma omp for
	        for (i = 0; i < ndata; i++) {
		    if (fabs(ddata[i] - missing_value) < limits) ddata[i] = UNDEFINED;
	        }
	    }
	    if (add_offset != 0.0 || scale_factor != 1.0) {
#pragma omp for
	        for (i = 0; i < ndata; i++) {
	            if (DEFINED_VAL(ddata[i])) {
		        data[i] = (float) ddata[i]*scale_factor + add_offset;
	            }
		    else {
		        data[i] = UNDEFINED;
		    }
	        }
	    }
	    else {
#pragma omp for
	        for (i = 0; i < ndata; i++) {
	            if (DEFINED_VAL(ddata[i])) {
		        data[i] = (float) ddata[i];
	            }
		    else {
		        data[i] = UNDEFINED;
		    }
	        }
	    }
	}

	free(ddata);
	use_scale = 0;
	/* close netcdf file */
        status = nc_close(ncid);
    }
    return 0;
}


#else
int f_import_netcdf(ARG3) {
    fatal_error("import_netcdf: not installed","");
    return 1;
}
#endif
