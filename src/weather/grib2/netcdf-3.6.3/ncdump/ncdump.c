/*********************************************************************
 *   Copyright 1993, University Corporation for Atmospheric Research
 *   See netcdf/README file for copying and redistribution conditions.
 *   $Header: /upc/share/CVS/netcdf-3/ncdump/ncdump.c,v 1.100 2008/06/05 23:00:15 russ Exp $
 *********************************************************************/

#include <config.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <assert.h>
#include <math.h>

#include <netcdf.h>
#include "ncdump.h"
#include "dumplib.h"
#include "vardata.h"
#include "indent.h"
#include "isnan.h"

#define int64_t long long
#define uint64_t unsigned long long

#define	STREQ(a, b)	(*(a) == *(b) && strcmp((a), (b)) == 0)

char *progname;

static void
usage(void)
{
#define USAGE   "\
  [-c]             Coordinate variable data and header information\n\
  [-h]             Header information only, no data\n\
  [-v var1[,...]]  Data for variable(s) <var1>,... only\n\
  [-b [c|f]]       Brief annotations for C or Fortran indices in data\n\
  [-f [c|f]]       Full annotations for C or Fortran indices in data\n\
  [-l len]         Line length maximum in data section (default 80)\n\
  [-n name]        Name for netCDF (default derived from file name)\n\
  [-p n[,n]]       Display floating-point values with less precision\n\
  [-x]             Output XML (NcML) instead of CDL\n\
  [-k]             Output kind of netCDF file\n\
  file             Name of netCDF file\n"

    (void) fprintf(stderr,
		   "%s [-c|-h] [-v ...] [[-b|-f] [c|f]] [-l len] [-n name] [-p n[,n]] [-x] [-k] file\n%s",
		   progname,
		   USAGE);
    
    (void) fprintf(stderr,
                 "netcdf library version %s\n",
                 nc_inq_libvers());
}


/* 
 * convert pathname of netcdf file into name for cdl unit, by taking 
 * last component of path and stripping off any extension.
 * DMH: add code to handle OPeNDAP url.
 * DMH: I think this also works for UTF8.
 */
static char *
name_path(const char *path)
{
    const char *cp;
    char *new;
    char *sp;

#ifdef vms
#define FILE_DELIMITER ']'
#endif    
#if defined(WIN32) || defined(msdos)
#define FILE_DELIMITER '\\'
#endif    
#ifndef FILE_DELIMITER /* default to unix */
#define FILE_DELIMITER '/'
#endif

#ifdef USE_DAP
    /* See if this is a url; note that it might
       be prefixed with dap parameters: [...] */
    /* Simulate the following regexp: (\[.*\])*http[s]?:// */
    int isurl=1;
    cp = path;
    while(*cp) {
        if(*cp == ' ' || *cp == '\t') {cp++; continue;}
        if(*cp == '[') {
            sp = strchr(cp,']');
            if(sp == NULL) {isurl=0; break;}
            cp = sp + 1;
        } else break;
    }
    if(isurl && (strncmp(cp,"http://",7)==0 || strncmp(cp,"https://",8)==0)) {
	/* Looks like a url, so we need to extract the relevant file part */
        /* In order to simplify, allocate the new space and modify the URL */
        new = (char *)emalloc((unsigned)(1+strlen(cp)));
        strcpy(new,cp);    
        sp = strrchr(new,'?'); /* find start of the constraints, if any */
        if(sp != NULL) {*sp = '\0';}
        /* do like below and remove one extension; if it does not exist,
           then technically, this a malformed dap url, but ignore */
        sp = strrchr(new, '/'); /* can never be null because its a url */
        sp++; /* past delimiter */
	/* overwrite prefix of the url */
        strcpy(new,sp); /* ok because sp is null terminated if original was */
	/* remove one trailing extension */
        if((sp = strrchr(new, '.')) != NULL) *sp = '\0';
        return new;
    }
#endif /*USE_DAP*/

    cp = strrchr(path, FILE_DELIMITER);
    if (cp == 0)		/* no delimiter */
      cp = path;
    else			/* skip delimeter */
      cp++;
    new = (char *) emalloc((unsigned) (strlen(cp)+1));
    (void) strncpy(new, cp, strlen(cp) + 1);	/* copy last component of path */
    if ((sp = strrchr(new, '.')) != NULL)
      *sp = '\0';		/* strip off any extension */
    return new;
}

/* Return primitive type name */
static const char *
prim_type_name(nc_type type)
{
    switch (type) {
      case NC_BYTE:
	return "byte";
      case NC_CHAR:
	return "char";
      case NC_SHORT:
	return "short";
      case NC_INT:
	return "int";
      case NC_FLOAT:
	return "float";
      case NC_DOUBLE:
	return "double";
#ifdef USE_NETCDF4
      case NC_UBYTE:
	return "ubyte";
      case NC_USHORT:
	return "ushort";
      case NC_UINT:
	return "uint";
      case NC_INT64:
	return "int64";
      case NC_UINT64:
	return "uint64";
      case NC_STRING:
	return "string";
      case NC_VLEN:
	return "vlen";
      case NC_OPAQUE:
	return "opaque";
      case NC_COMPOUND:
	return "compound";
#endif /* USE_NETCDF4 */
      default:
	error("prim_type_name: bad type %d", type);
	return "bogus";
    }
}


/*
 * Remove trailing zeros (after decimal point) but not trailing decimal
 * point from ss, a string representation of a floating-point number that
 * might include an exponent part.
 */
static void
tztrim(char *ss)
{
    char *cp, *ep;
    
    cp = ss;
    if (*cp == '-')
      cp++;
    while(isdigit((int)*cp) || *cp == '.')
      cp++;
    if (*--cp == '.')
      return;
    ep = cp+1;
    while (*cp == '0')
      cp--;
    cp++;
    if (cp == ep)
      return;
    while (*ep)
      *cp++ = *ep++;
    *cp = '\0';
    return;
}


/* 
 * Emit kind of netCDF file
 */
static void 
do_nckind(int ncid, const char *path)
{
    int nc_kind;
    char *kind_str;
  
   /*nc_set_log_level(3);*/
    
    NC_CHECK( nc_inq_format(ncid, &nc_kind) );
    switch(nc_kind) {
    case NC_FORMAT_CLASSIC:
	kind_str = "classic";
	break;
    case NC_FORMAT_64BIT:
	kind_str = "64-bit offset";
	break;
    case NC_FORMAT_NETCDF4:
	kind_str = "netCDF-4";
	break;
    case NC_FORMAT_NETCDF4_CLASSIC:
	kind_str = "netCDF-4 classic model";
	break;
    default:
	kind_str = "unrecognized";
	error("unrecognized format: %s", path);
	break;
    }
    printf ("%s\n", kind_str);

    NC_CHECK( nc_close(ncid) );
}


/* 
 * Emit initial line of output for NcML
 */
static void 
pr_initx(int ncid, const char *path)
{
    printf("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<netcdf xmlns=\"http://www.unidata.ucar.edu/namespaces/netcdf/ncml-2.2\" location=\"%s\">\n", 
	   path);
}


/*
 * Print attribute string, for text attributes.
 */
static void
pr_att_string(
    int kind,
    size_t len,
    const char *string
    )
{
    int iel;
    const char *cp;
    const char *sp;
    unsigned char uc;

    cp = string;
    printf ("\"");
    /* adjust len so trailing nulls don't get printed */
    sp = cp + len - 1;
    while (len != 0 && *sp-- == '\0')
	len--;
    for (iel = 0; iel < len; iel++)
	switch (uc = *cp++ & 0377) {
	case '\b':
	    printf ("\\b");
	    break;
	case '\f':
	    printf ("\\f");
	    break;
	case '\n':		
	    /* Only generate linebreaks after embedded newlines for
	     * classic, 64-bit offset, or classic model files.  For
	     * netCDF-4 files, don't generate linebreaks, because that
	     * would create an extra string in a list of strings.  */
	    if (kind != NC_FORMAT_NETCDF4) {
		printf ("\\n\",\n\t\t\t\"");
	    } else {
		printf("\\n");
	    }
	    break;
	case '\r':
	    printf ("\\r");
	    break;
	case '\t':
	    printf ("\\t");
	    break;
	case '\v':
	    printf ("\\v");
	    break;
	case '\\':
	    printf ("\\\\");
	    break;
	case '\'':
	    printf ("\\'");
	    break;
	case '\"':
	    printf ("\\\"");
	    break;
	default:
	    if (iscntrl(uc))
	        printf ("\\%03o",uc);
	    else
	        printf ("%c",uc);
	    break;
	}
    printf ("\"");

}


/*
 * Print NcML attribute string, for text attributes.
 */
static void
pr_attx_string(
     size_t len,
     const char *string
     )
{
    int iel;
    const char *cp;
    const char *sp;
    unsigned char uc;

    cp = string;
    printf ("\"");
    /* adjust len so trailing nulls don't get printed */
    sp = cp + len - 1;
    while (len != 0 && *sp-- == '\0')
	len--;
    for (iel = 0; iel < len; iel++)
	switch (uc = *cp++ & 0377) {
	case '\"':
	    printf ("&quot;");
	    break;
	case '<':
	    printf ("&lt;");
	    break;
	case '>':
	    printf ("&gt;");
	    break;
	case '&':
	    printf ("&amp;");
	    break;
	case '\n':
	    printf ("&#xA;");
	    break;
	case '\r':
	    printf ("&#xD;");
	    break;
	case '\t':
	    printf ("&#x9;");
	    break;
	default:
	    if (iscntrl(uc))
	        printf ("&#%d;",uc);
	    else
	        printf ("%c",uc);
	    break;
	}
    printf ("\"");

}


/*
 * Print list of attribute values, for attributes of primitive types.
 * Attribute values must be printed with explicit type tags for
 * netCDF-3 primitive types, because CDL doesn't require explicit
 * syntax to declare such attribute types.  
 */
static void
pr_att_valgs(
    int kind,
    nc_type type,
    size_t len,
    const void *vals
    )
{
    int iel;
    signed char sc;
    short ss;
    int ii;
    char gps[PRIM_LEN];
    float ff;
    double dd;
#ifdef USE_NETCDF4
    unsigned char uc;
    unsigned short us;
    unsigned int ui;
    int64_t i64;
    uint64_t ui64;
    char *stringp;
#endif /* USE_NETCDF4 */
    char *delim = ", ";	/* delimiter between output values */

    if (len == 0)
	return;
    if (type == NC_CHAR) {
	char *cp = (char *) vals;
	pr_att_string(kind, len, cp);
	return;
    }
    /* else */
    for (iel = 0; iel < len; iel++) {
	if (iel == len - 1)
	    delim = "";
	switch (type) {
	case NC_BYTE:
	    sc = ((signed char *) vals)[iel];
	    printf ("%db%s", sc, delim);
	    break;
	case NC_SHORT:
	    ss = ((short *) vals)[iel];
	    printf ("%ds%s", ss, delim);
	    break;
	case NC_INT:
	    ii = ((int *) vals)[iel];
	    printf ("%d%s", ii, delim);
	    break;
	case NC_FLOAT:
	    ff = ((float *) vals)[iel];
	    if(isfinite(ff)) {
		int res;
		res = snprintf(gps, PRIM_LEN, float_att_fmt, ff);
		assert(res < PRIM_LEN);
		tztrim(gps);	/* trim trailing 0's after '.' */
		printf ("%s%s", gps, delim);
	    } else {
		if(isnan(ff)) {
		    printf("NaNf%s", delim);
		} else if(isinf(ff)) {
		    if(ff < 0.0f) {
			printf("-");
		    }
		    printf("Infinityf%s", delim);
		}
	    }
	    break;
	case NC_DOUBLE:
	    dd = ((double *) vals)[iel];
	    if(isfinite(dd)) {
		int res;
		res = snprintf(gps, PRIM_LEN, double_att_fmt, dd);
		assert(res < PRIM_LEN);
		tztrim(gps);
		printf ("%s%s", gps, delim);
	    } else {
		if(isnan(dd)) {
		    printf("NaN%s", delim);
		} else if(isinf(dd)) {
		    if(dd < 0.0) {
			printf("-");
		    }
		    printf("Infinity%s", delim);
		}
	    }
	    break;
#ifdef USE_NETCDF4
	case NC_UBYTE:
	    uc = ((unsigned char *) vals)[iel];
	    printf ("%udub%s", uc, delim);
	    break;
	case NC_USHORT:
	    us = ((unsigned short *) vals)[iel];
	    printf ("%huus%s", us, delim);
	    break;
	case NC_UINT:
	    ui = ((unsigned int *) vals)[iel];
	    printf ("%u%s", ui, delim);
	    break;
	case NC_INT64:
	    i64 = ((int64_t *) vals)[iel];
	    printf ("%lldL%s", i64, delim);
	    break;
	case NC_UINT64:
	    ui64 = ((uint64_t *) vals)[iel];
	    printf ("%lluUL%s", ui64, delim);
	    break;
	case NC_STRING:
	    stringp = ((char **) vals)[iel];
	    pr_att_string(kind, strlen(stringp), stringp);
	    printf("%s", delim);
	    break;
#endif /* USE_NETCDF4 */
	default:
	    error("pr_att_vals: bad type");
	}
    }
}


/*
 * Print list of numeric attribute values to string for use in NcML output.
 * Unlike CDL, NcML makes type explicit, so don't need type suffixes.
 */
static void
pr_att_valsx(
     nc_type type,
     size_t len,
     const double *vals,
     char *attvals,		/* returned string */
     size_t attvalslen		/* size of attvals buffer, assumed
				   large enough to hold all len
				   blank-separated values */
     )
{
    int iel;
    float ff;
    double dd;
    int ii;
#ifdef USE_NETCDF4
    unsigned int ui;
    int64_t i64;
    uint64_t ui64;
#endif /* USE_NETCDF4 */

    attvals[0]='\0';
    if (len == 0)
	return;
    for (iel = 0; iel < len; iel++) {
	char gps[PRIM_LEN];
	int res;
	switch (type) {
	case NC_BYTE:
	case NC_SHORT:
	case NC_INT:
	    ii = vals[iel];
	    res = snprintf(gps, PRIM_LEN, "%d", ii);
	    assert(res < PRIM_LEN);
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
#ifdef USE_NETCDF4
	case NC_UBYTE:
	case NC_USHORT:
	case NC_UINT:
	    ui = vals[iel];
	    res = snprintf(gps, PRIM_LEN, "%u", ui);
	    assert(res < PRIM_LEN);
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
	case NC_INT64:
	    i64 = vals[iel];
	    res = snprintf(gps, PRIM_LEN, "%lld", i64);
	    assert(res < PRIM_LEN);
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
	case NC_UINT64:
	    ui64 = vals[iel];
	    res = snprintf(gps, PRIM_LEN, "%llu", ui64);
	    assert(res < PRIM_LEN);
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
#endif /* USE_NETCDF4 */
	case NC_FLOAT:
	    ff = vals[iel];
	    res = snprintf(gps, PRIM_LEN, float_attx_fmt, ff);
	    assert(res < PRIM_LEN);
	    tztrim(gps);	/* trim trailing 0's after '.' */
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
	case NC_DOUBLE:
	    dd = vals[iel];
	    res = snprintf(gps, PRIM_LEN, double_att_fmt, dd);
	    assert(res < PRIM_LEN);
	    tztrim(gps);	/* trim trailing 0's after '.' */
	    (void) strlcat(attvals, gps, attvalslen);
	    (void) strlcat(attvals, iel < len-1 ? " " : "", attvalslen);
	    break;
	default:
	    error("pr_att_valsx: bad type");
	}
    }
}

/* 
 * Return name of type in user-allocated space, whether built-in
 * primitive type or user-defined type.  Note: name must have enough
 * space allocated to hold type name.
 */
static void
get_type_name(int ncid, nc_type type, char *name)
{
#ifdef USE_NETCDF4
    if (is_user_defined_type(type)) {
	nc_inq_user_type(ncid, type, name, NULL, NULL, NULL, NULL);
    } else {
	strncpy(name, prim_type_name(type), NC_MAX_NAME + 1);
    }
#else
    strncpy(name, prim_type_name(type), NC_MAX_NAME + 1);
#endif /* USE_NETCDF4 */
}

/* 
 * Print a variable attribute
 */
static void
pr_att(
    int ncid,
    int kind,
    int varid,
    const char *varname,
    int ia
    )
{
    ncatt_t att;			/* attribute */
	    
    NC_CHECK( nc_inq_attname(ncid, varid, ia, att.name) );
    NC_CHECK( nc_inq_att(ncid, varid, att.name, &att.type, &att.len) );
    att.tinfo = get_typeinfo(att.type);

    indent_out();
    printf ("\t\t");
    if (is_user_defined_type(att.type)) {
	char att_type_name[NC_MAX_NAME + 1];
	get_type_name(ncid, att.type, att_type_name);
	/* printf ("\t\t%s ", att_type_name); */
	/* ... but handle special characters in CDL names with escapes */
	print_name(att_type_name);
	printf(" ");
    }
    /* 	printf ("\t\t%s:%s = ", varname, att.name); */
    print_name(varname);
    printf(":");
    print_name(att.name);
    printf(" = ");

    if (att.len == 0) {	/* show 0-length attributes as empty strings */
	att.type = NC_CHAR;
    }

    if (! is_user_defined_type(att.type) ) {
	att.valgp = (void *) emalloc((att.len + 1) * att.tinfo->size );
	NC_CHECK( nc_get_att(ncid, varid, att.name, att.valgp ) );
	if(att.type == NC_CHAR)	/* null-terminate retrieved text att value */
	    ((char *)att.valgp)[att.len] = '\0';
	pr_att_valgs(kind, att.type, att.len, att.valgp);
#ifdef USE_NETCDF4
	/* If NC_STRING, need to free all the strings also */
	if(att.type == NC_STRING) {
	    int i;
	    for(i = 0; i < att.len; i++) {
		nc_free_string(att.len, att.valgp);
	    }
	}
#endif /* USE_NETCDF4 */
	free(att.valgp);
    }
#ifdef USE_NETCDF4
    else /* User-defined type. */
    {
       char type_name[NC_MAX_NAME + 1];
       size_t type_size, nfields;
       nc_type base_nc_type;
       int class, i;
       void *data;

       NC_CHECK( nc_inq_user_type(ncid, att.type,  type_name, &type_size, 
				  &base_nc_type, &nfields, &class));
       switch(class)
       {
	  case NC_VLEN:
	      /* because size returned for vlen is base type size, but we
	       * need space to read array of vlen structs into ... */
	     data = emalloc(att.len * sizeof(nc_vlen_t));
	     break;
	  case NC_OPAQUE:
	      data = emalloc(att.len * type_size);
	     break;
	  case NC_ENUM:
	      /* a long long is ample for all base types */
	     data = emalloc(att.len * sizeof(int64_t));
	     break;
	  case NC_COMPOUND:
	      data = emalloc(att.len * type_size);
	     break;
	  default:
	     error("unrecognized class of user defined type: %d", class);
       }

       NC_CHECK( nc_get_att(ncid, varid, att.name, data));

       switch(class) {
       case NC_VLEN:
	   pr_any_att_vals(&att, data);
	   free(data);
	   break;
       case NC_OPAQUE: {
	   char *sout = emalloc(2 * type_size + 1);
	   unsigned char *cp = data;
	   for (i = 0; i < att.len; i++) {
	       (void) ncopaque_val_as_hex(type_size, sout, cp);
	       printf("%s%s", sout, i < att.len-1 ? ", " : "");
	       cp += type_size;
	   }
	   free(sout);
       }
	   break;
       case NC_ENUM: {
	   int64_t value;
	   for (i = 0; i < att.len; i++) {
	       char enum_name[NC_MAX_NAME + 1];
	       switch(base_nc_type)
	       {
	       case NC_BYTE:
		   value = *((char *)data + i);
		   break;
	       case NC_UBYTE:
		   value = *((unsigned char *)data + i);
		   break;
	       case NC_SHORT:
		   value = *((short *)data + i);
		   break;
	       case NC_USHORT:
		   value = *((unsigned short *)data + i);
		   break;
	       case NC_INT:
		   value = *((int *)data + i);
		   break;
	       case NC_UINT:
		   value = *((unsigned int *)data + i);
		   break;
	       case NC_INT64:
		   value = *((int64_t *)data + i);
		   break;
	       case NC_UINT64:
		   value = *((uint64_t *)data + i);
		   break;
	       }
	       NC_CHECK( nc_inq_enum_ident(ncid, att.type, value, 
					   enum_name));
/* 	       printf("%s%s", enum_name, i < att.len-1 ? ", " : ""); */
	       print_name(enum_name);
	       printf("%s", i < att.len-1 ? ", " : "");
	   }
       }
	   break;
       case NC_COMPOUND:
	   pr_any_att_vals(&att, data);
	   free(data);
	   break;
       default:
	   error("unrecognized class of user defined type: %d", class);
       }
    }
#endif /* USE_NETCDF4 */

    printf (" ;\n");
}

/* 
 * Print a variable attribute for NcML
 */
static void
pr_attx(
    int ncid,
    int varid,
    int ia
    )
{
    ncatt_t att;			/* attribute */
    char *attvals;
    int attvalslen = 0;

    NC_CHECK( nc_inq_attname(ncid, varid, ia, att.name) );
    NC_CHECK( nc_inq_att(ncid, varid, att.name, &att.type, &att.len) );
    att.tinfo = get_typeinfo(att.type);

    /* Put attribute values into a single string, with blanks in between */

    switch (att.type) {
    case NC_CHAR:
	attvals = (char *) emalloc(att.len + 1);
	attvalslen = att.len;
	attvals[att.len] = '\0';
	NC_CHECK( nc_get_att_text(ncid, varid, att.name, attvals ) );
	break;
#ifdef USE_NETCDF4
    case NC_STRING:
	/* TODO: this only prints first string value, need to handle
	   multiple strings? */
	attvals = (char *) emalloc(att.len + 1);
	attvals[att.len] = '\0';
	NC_CHECK( nc_get_att_text(ncid, varid, att.name, attvals ) );
	break;
    case NC_VLEN:
	/* TODO */
	break;
    case NC_OPAQUE:
	/* TODO */
	break;
    case NC_COMPOUND:
	/* TODO */
	break;
#endif /* USE_NETCDF4 */
    default:
	att.vals = (double *) emalloc((att.len + 1) * sizeof(double));
	NC_CHECK( nc_get_att_double(ncid, varid, att.name, att.vals ) );
	attvalslen = 20*att.len; /* max 20 chars for each value and blank separator */
	attvals = (char *) emalloc(attvalslen + 1);
	pr_att_valsx(att.type, att.len, att.vals, attvals, attvalslen);
	free(att.vals); 
	break;
    }

    /* Don't output type for string attributes, since that's default type */
    if(att.type == NC_CHAR
#ifdef USE_NETCDF4
                          || att.type == NC_CHAR
#endif /* USE_NETCDF4 */
       ) {
	/* TODO: XML-ish escapes for special chars in names */
	printf ("%s  <attribute name=\"%s\" value=", 
		varid != NC_GLOBAL ? "  " : "", 
		att.name);
	/* print attvals as a string with XML escapes */
	pr_attx_string(attvalslen, attvals);
    } else {			/* non-string attribute */
	char att_type_name[NC_MAX_NAME + 1];
	get_type_name(ncid, att.type, att_type_name);
	printf ("%s  <attribute name=\"%s\" type=\"%s\" value=\"", 
		varid != NC_GLOBAL ? "  " : "", 
		att.name, 
		att_type_name);
	printf("%s\"",attvals);
    }
    printf (" />\n");
    free (attvals);
}


/* Print optional NcML attribute for a variable's shape */
static void
pr_shape(ncvar_t* varp, ncdim_t *dims)
{
    char *shape;
    int shapelen = 0;
    int id;

    if (varp->ndims == 0)
	return;
    for (id = 0; id < varp->ndims; id++) {
	shapelen += strlen(dims[varp->dims[id]].name) + 1;
    }
    shape = (char *) emalloc(shapelen);
    shape[0] = '\0';
    for (id = 0; id < varp->ndims; id++) {
	/* TODO: XML-ish escapes for special chars in dim names */
	strlcat(shape, dims[varp->dims[id]].name, shapelen);
	strlcat(shape, id < varp->ndims-1 ? " " : "", shapelen);
    }
    printf (" shape=\"%s\"", shape);
    free(shape);
}

#ifdef USE_NETCDF4


/* Print an enum type declaration */
static void
print_enum_type(int ncid, nc_type typeid) {
    char type_name[NC_MAX_NAME + 1];
    size_t type_size;
    nc_type base_nc_type;
    size_t type_nfields;
    int type_class;
    char base_type_name[NC_MAX_NAME + 1];
    int f;
    int64_t memval;
    char memname[NC_MAX_NAME + 1];
 /* extra space for escapes, and punctuation */
#define SAFE_BUF_LEN 4*NC_MAX_NAME+30
    char safe_buf[SAFE_BUF_LEN];
    char *delim;
    int64_t data;	    /* space for data of any primitive type */
    char *esc_btn;
    char *esc_tn;
    char *esc_mn;
    int res;

    NC_CHECK( nc_inq_user_type(ncid, typeid, type_name, &type_size, &base_nc_type, 
			       &type_nfields, &type_class) );

    get_type_name(ncid, base_nc_type, base_type_name); 
    indent_out();
    esc_btn = escaped_name(base_type_name);
    esc_tn = escaped_name(type_name);
    res = snprintf(safe_buf, SAFE_BUF_LEN,"%s enum %s {", esc_btn, esc_tn);
    assert(res < SAFE_BUF_LEN);
    free(esc_btn);
    free(esc_tn);
    lput(safe_buf);
    delim = ", ";
    for (f = 0; f < type_nfields; f++) {
	if (f == type_nfields - 1)
	    delim = "} ;\n";
	NC_CHECK( nc_inq_enum_member(ncid, typeid, f, memname, &data) );
	switch (base_nc_type) {
	case NC_BYTE:
	    memval = *(char *)&data;
	    break;
	case NC_SHORT:
	    memval = *(short *)&data;
	    break;
	case NC_INT:
	    memval = *(int *)&data;
	    break;
#ifdef USE_NETCDF4
	case NC_UBYTE:
	    memval = *(unsigned char *)&data;
	    break;
	case NC_USHORT:
	    memval = *(unsigned short *)&data;
	    break;
	case NC_UINT:
	    memval = *(unsigned int *)&data;
	    break;
	case NC_INT64:
	    memval = *(int64_t *)&data;
	    break;
	case NC_UINT64:
	    memval = *(uint64_t *)&data;
	    break;
#endif /* USE_NETCDF4 */
	default:
	    error("\tBad base type for enum!\n");
	    break;
	}
	esc_mn = escaped_name(memname);
	res = snprintf(safe_buf, SAFE_BUF_LEN, "%s = %lld%s", memname, 
		       memval, delim);
	assert(res < SAFE_BUF_LEN);
	free(esc_mn);
	lput(safe_buf);
    }
}


/* Print a user-defined type declaration */
static void
print_ud_type(int ncid, nc_type typeid) {
    
    char type_name[NC_MAX_NAME + 1];
    char base_type_name[NC_MAX_NAME + 1];
    size_t type_nfields, type_size;
    nc_type base_nc_type;
    int f, type_class;
    
    NC_CHECK( nc_inq_user_type(ncid, typeid, type_name, &type_size, &base_nc_type, 
			       &type_nfields, &type_class) );
    switch(type_class) {
    case NC_VLEN:
	get_type_name(ncid, base_nc_type, base_type_name);
	indent_out();
/* 	printf("%s(*) %s ;\n", base_type_name, type_name); */
	print_name(base_type_name);
	printf("(*) ");
	print_name(type_name);
	printf(" ;\n");
	break;
    case NC_OPAQUE:
	indent_out();
/* 	printf("opaque(%d) %s ;\n", (int)type_size, type_name); */
	printf("opaque(%d) ", (int)type_size);
	print_name(type_name);
	printf(" ;\n");
	break;
    case NC_ENUM:
	print_enum_type(ncid, typeid);
	break;
    case NC_COMPOUND:
	{
	    char field_name[NC_MAX_NAME + 1];
	    char field_type_name[NC_MAX_NAME + 1];
	    size_t field_offset;
	    nc_type field_type;
	    int field_ndims, field_dim_sizes[NC_MAX_DIMS];
	    int d;
	    
	    indent_out();
/* 	    printf("compound %s {\n", type_name); */
	    printf("compound ");
	    print_name(type_name);
	    printf(" {\n");
	    for (f = 0; f < type_nfields; f++)
		{
		    NC_CHECK( nc_inq_compound_field(ncid, typeid, f, field_name, 
						    &field_offset, &field_type, &field_ndims,
						    field_dim_sizes) );
		    get_type_name(ncid, field_type, field_type_name);
		    indent_out();
/* 		    printf("  %s %s", field_type_name, field_name); */
		    printf("  ");
		    print_name(field_type_name);
		    printf(" ");
		    print_name(field_name);
		    if (field_ndims > 0) {
			printf("(");
			for (d = 0; d < field_ndims-1; d++)
			    printf("%d, ", field_dim_sizes[d]);
			printf("%d)", field_dim_sizes[field_ndims-1]);
		    }
		    printf(" ;\n");
		}
            indent_out();
/* 	    printf("} // %s\n", type_name); */
	    printf("} // ");
	    print_name(type_name);
	    printf("\n");
	}
	break;
    default:
	error("\tUnknown class of user-defined type!\n");
    }
}
#endif /* USE_NETCDF4 */

/* Recursively dump the contents of a group. (Recall that only
 * netcdf-4 format files can have groups. On all other formats, there
 * is just a root group, so recursion will not take place.) */
static void
do_ncdump_rec(int ncid, const char *path, fspec_t* specp)
{
   int ndims;			/* number of dimensions */
   int nvars;			/* number of variables */
   int ngatts;			/* number of global attributes */
   int xdimid;			/* id of unlimited dimension */
   int nunlim;			/* number of unlimited dimensions */
   int varid;			/* variable id */
   ncdim_t *dims;		/* dimensions */
   size_t *vdims=0;	        /* dimension sizes for a single variable */
   ncvar_t var;			/* variable */
   ncatt_t att;			/* attribute */
   int id;			/* dimension number per variable */
   int ia;			/* attribute number */
   int iv;			/* variable number */
   vnode* vlist = 0;		/* list for vars specified with -v option */
   int nc_status;		/* return from netcdf calls */
   char type_name[NC_MAX_NAME + 1];
   int kind;		/* strings output differently for nc4 files */
#ifdef USE_NETCDF4
   int *dimids_grp;	        /* dimids of the dims in this group. */
   int *unlimids;		/* dimids of unlimited dimensions in this group */
   int varids_grp[NC_MAX_VARS]; /* varids of the vars in this group. */
   int d_grp, ndims_grp;
   int v_grp, nvars_grp;
   char dim_name[NC_MAX_NAME + 1];
   size_t len;
   int ntypes, *typeids;
#else
   int dimid;			/* dimension id */
#endif /* USE_NETCDF4 */

   /*
    * If any vars were specified with -v option, get list of
    * associated variable ids.  Assume vars specified with syntax like
    * "grp1/grp2/varname" if they are in groups.
    */
   if (specp->nlvars > 0) {
      vlist = newvlist();	/* list for vars specified with -v option */
      for (iv=0; iv < specp->nlvars; iv++) {
	  /* Should just use nc_inq_varid(), but it doesn't understand
	   * group syntas like "grp1/grp2/var" yet, so call intermediate
	   * recursive function instead. */
	 NC_CHECK( nc_inq_gvarid(ncid, specp->lvars[iv], &varid) );
	 varadd(vlist, varid);
      }
   }

#ifdef USE_NETCDF4
   /* Are there any user defined types in this group? */
   NC_CHECK( nc_inq_typeids(ncid, &ntypes, NULL) );
   if (ntypes)
   {
      int t;

      typeids = emalloc(ntypes * sizeof(int));
      NC_CHECK( nc_inq_typeids(ncid, &ntypes, typeids) );
      indent_out();
      printf("types:\n");
      indent_more();
      for (t = 0; t < ntypes; t++)
      {
	 print_ud_type(ncid, typeids[t]); /* print declaration of user-defined type */
      }
      indent_less();
      free(typeids);
   }
#endif /* USE_NETCDF4 */

   /*
    * get number of dimensions, number of variables, number of global
    * atts, and dimension id of unlimited dimension, if any
    */
   NC_CHECK( nc_inq(ncid, &ndims, &nvars, &ngatts, &xdimid) );
   /* get dimension info */
   dims = (ncdim_t *) emalloc((ndims + 1) * sizeof(ncdim_t));
   if (ndims > 0) {
       indent_out();
       printf ("dimensions:\n");
   }

#ifdef USE_NETCDF4
   /* In netCDF-4 files, dimids will not be sequential because they
    * may be defined in various groups, and we are only looking at one
    * group at a time. */

   /* Find the number of dimids defined in this group. */
   NC_CHECK( nc_inq_ndims(ncid, &ndims_grp) );
   dimids_grp = (int *)emalloc((ndims_grp + 1) * sizeof(int));
   
   /* Find the dimension ids in this group. */
   NC_CHECK( nc_inq_dimids(ncid, 0, dimids_grp, 0) );

   /* Find the number of unlimited dimensions and get their IDs */
   NC_CHECK( nc_inq_unlimdims(ncid, &nunlim, NULL) );
   unlimids = (int *)emalloc((nunlim + 1) * sizeof(int));
   NC_CHECK( nc_inq_unlimdims(ncid, &nunlim, unlimids) );
    
   /* For each dimension defined in this group, learn, and print out
    * info. */
   for (d_grp = 0; d_grp < ndims_grp; d_grp++)
   {
      int dimid = dimids_grp[d_grp];
      int is_unlimited = 0;
      int uld;

      for (uld = 0; uld < nunlim; uld++) {
	  if(dimid == unlimids[uld]) {
	      is_unlimited = 1;
	      break;
	  }	  
      }
      NC_CHECK( nc_inq_dim(ncid, dimid, dims[d_grp].name, &dims[d_grp].size) );

      indent_out();
      printf ("\t");
      print_name(dims[d_grp].name);
      printf (" = ");
      if (is_unlimited) {
	  printf ("UNLIMITED ; // (%u currently)\n", 
		  (unsigned int)dims[d_grp].size);
      } else {
	  printf ("%u ;\n", (unsigned int)dims[d_grp].size);
      }
   }
   if(dimids_grp)
       free(dimids_grp);
#else /* not using netCDF-4 */
   for (dimid = 0; dimid < ndims; dimid++) {
      NC_CHECK( nc_inq_dim(ncid, dimid, dims[dimid].name, &dims[dimid].size) );
      indent_out();
      printf ("\t");
      print_name(dims[dimid].name);
      printf (" = ");
      if (dimid == xdimid) {
	  printf ("UNLIMITED ; // (%u currently)\n", 
		  (unsigned int)dims[dimid].size);
      } else {
	  printf ("%u ;\n", (unsigned int)dims[dimid].size);
      }
   }
#endif /* USE_NETCDF4 */

   if (nvars > 0) {
       indent_out();
       printf ("variables:\n");
   }
   /* Because netCDF-4 can have a string attribute with multiple
    * string values, we can't output strings with embedded newlines
    * as what look like multiple strings, as we do for classic and
    * 64-bit offset files.  So we need to know the output file type
    * to know how to print strings with embedded newlines. */
   NC_CHECK( nc_inq_format(ncid, &kind) );
       
#ifdef USE_NETCDF4
   /* In netCDF-4 files, varids will not be sequentially numbered
    * because they may be defined in various groups, and we are only
    * looking at one group at a time. */

   /* Find the number of varids defined in this group, and their ids. */
   NC_CHECK( nc_inq_varids(ncid, &nvars_grp, varids_grp) );
    
   /* For each var defined in this group, learn, and print out
    * info. */
   for (v_grp = 0; v_grp < nvars_grp; v_grp++)
   {
       varid = varids_grp[v_grp];
      /* Learn about the var and its dimension ids. */
      NC_CHECK( nc_inq_varndims(ncid, varid, &var.ndims) );
      var.dims = (int *) emalloc((var.ndims + 1) * sizeof(int));
      NC_CHECK( nc_inq_var(ncid, varid, var.name, &var.type, 0,
			   var.dims, &var.natts) );
      get_type_name(ncid, var.type, type_name);
      var.tinfo = get_typeinfo(var.type);
      /* Display the var info for the user. */
      indent_out();
/*       printf ("\t%s %s", type_name, var.name); */
      printf ("\t");
      print_name (type_name);
      printf (" ");
      print_name (var.name);
      if (var.ndims > 0)
	 printf ("(");
      for (id = 0; id < var.ndims; id++) 
      {
	 /* This dim may be in a parent group, so let's look up the
	  * name. */
	 NC_CHECK( nc_inq_dimname(ncid, var.dims[id], dim_name) );
/* 	 printf ("%s%s", dim_name, id < var.ndims-1 ? ", " : ")"); */
	 print_name (dim_name);
	 printf ("%s", id < var.ndims-1 ? ", " : ")");
      }
      printf (" ;\n");

      /* print variable attributes */
      for (ia = 0; ia < var.natts; ia++) { /* print ia-th attribute */
	  pr_att(ncid, kind, varids_grp[v_grp], var.name, ia);
      }
      free(var.dims);
   }
#else /* not using netCDF-4 */
   /* get variable info, with variable attributes */
   for (varid = 0; varid < nvars; varid++) {
      NC_CHECK( nc_inq_varndims(ncid, varid, &var.ndims) );
      var.dims = (int *) emalloc((var.ndims + 1) * sizeof(int));
      NC_CHECK( nc_inq_var(ncid, varid, var.name, &var.type, 0,
			   var.dims, &var.natts) );
      get_type_name(ncid, var.type, type_name);
      var.tinfo = get_typeinfo(var.type);
      indent_out();
/*       printf ("\t%s %s", type_name, var.name); */
      printf ("\t");
      print_name (type_name);
      printf (" ");
      print_name (var.name);
      if (var.ndims > 0)
	 printf ("(");
      for (id = 0; id < var.ndims; id++) {
/* 	 printf ("%s%s", dims[var.dims[id]].name, id < var.ndims-1 ? ", " : ")"); */
	 print_name (dims[var.dims[id]].name);
	 printf ("%s", id < var.ndims-1 ? ", " : ")");
      }
      printf (" ;\n");

      /* print variable attributes */
      for (ia = 0; ia < var.natts; ia++) { /* print ia-th attribute */
	  pr_att(ncid, kind, varid, var.name, ia);
      }
      free(var.dims);
   }
#endif /* USE_NETCDF4 */

   /* get global attributes */
   if (ngatts > 0) {
      printf ("\n");
      indent_out();
      printf ("// global attributes:\n");
   }
   for (ia = 0; ia < ngatts; ia++) { /* print ia-th global attribute */
       pr_att(ncid, kind, NC_GLOBAL, "", ia);
   }
    
   if (! specp->header_only) {
      if (nvars > 0) {
	  indent_out();
	  printf ("data:\n");
      }
#ifdef USE_NETCDF4
      /* output variable data */
      for (v_grp = 0; v_grp < nvars_grp; v_grp++)
      {
	 void *fillvalp;
	 varid = varids_grp[v_grp];
	 /* if var list specified, test for membership */
	 if (specp->nlvars > 0 && ! varmember(vlist, varid))
	    continue;
	 NC_CHECK( nc_inq_varndims(ncid, varid, &var.ndims) );
	 var.dims = (int *) emalloc((var.ndims + 1) * sizeof(int));
	 NC_CHECK( nc_inq_var(ncid, varid, var.name, &var.type, 0,
			      var.dims, &var.natts) );
	 var.tinfo = get_typeinfo(var.type);
	 /* If coords-only option specified, don't get data for
	  * non-coordinate vars */
	 if (specp->coord_vals && !iscoordvar(ncid,varid)) {
	    continue;
	 }

	 /* Don't get data for record variables if no records have
	  * been written yet */
	 if (isrecvar(ncid, varid) && dims[xdimid].size == 0) {
	    continue;
	 }
		
	 /* Collect variable's dim sizes */
	 if (vdims) {
	     free(vdims);
	     vdims = 0;
	 }
	 vdims = (size_t *) emalloc((var.ndims + 1) * sizeof(size_t));
	 for (id = 0; id < var.ndims; id++)
	 {
	    NC_CHECK( nc_inq_dimlen(ncid, var.dims[id], &len) );
	    vdims[id] = len;
	 }
	 var.has_fillval = 1; /* by default, but turn off for bytes */
	    
	 /* get _FillValue attribute */
	 nc_status = nc_inq_att(ncid,varid,_FillValue,&att.type,&att.len);
	 fillvalp = emalloc(var.tinfo->size);
	 if(nc_status == NC_NOERR &&
	    att.type == var.type && att.len == 1) {
	     NC_CHECK(nc_get_att(ncid, varid, _FillValue, fillvalp));
	 } else {
	     switch (var.type) {
	     case NC_BYTE:
		 /* don't do default fill-values for bytes, too risky */
		 var.has_fillval = 0;
		 fillvalp = 0;
		 break;
	     case NC_CHAR:
		 *(char *)fillvalp = NC_FILL_CHAR;
		 break;
	     case NC_SHORT:
		 *(short *)fillvalp = NC_FILL_SHORT;
		 break;
	     case NC_INT:
		 *(int *)fillvalp = NC_FILL_INT;
		 break;
	     case NC_FLOAT:
		 *(float *)fillvalp = NC_FILL_FLOAT;
		 break;
	     case NC_DOUBLE:
		 *(double *)fillvalp = NC_FILL_DOUBLE;
		 break;
	     case NC_UBYTE:
		 *(unsigned char *)fillvalp = NC_FILL_UBYTE;
		 break;
	     case NC_USHORT:
		 *(unsigned short *)fillvalp = NC_FILL_USHORT;
		 break;
	     case NC_UINT:
		 *(unsigned int *)fillvalp = NC_FILL_UINT;
		 break;
	     case NC_INT64:
		 *(int64_t *)fillvalp = NC_FILL_INT64;
		 break;
	     case NC_UINT64:
		 *(uint64_t *)fillvalp = NC_FILL_UINT64;
		 break;
	     case NC_STRING:
		 *((char **)fillvalp) = NC_FILL_STRING;
		 break;
	     default:		/* no default fill values for
				   user-defined types */
		 var.has_fillval = 0;
		 fillvalp = 0;
		 break;
	     }
	 }
	 var.fillvalp = fillvalp;
	 /* printf format used to print each value */
	 var.fmt = get_fmt(ncid, varid, var.type);
	 var.locid = ncid;
	 set_tostring_func(&var);
	 if (vardata(&var, vdims, ncid, varid, specp) == -1) {
	    error("can't output data for variable %s", var.name);
	    NC_CHECK(
	       nc_close(ncid) );
	    if (vlist)
	       free(vlist);
	    return;
	 }
      }
#else /* not using netCDF-4 */
      /* output variable data */
      for (varid = 0; varid < nvars; varid++) {
	 void *fillvalp;
	 /* if var list specified, test for membership */
	 if (specp->nlvars > 0 && ! varmember(vlist, varid))
	    continue;
	 NC_CHECK( nc_inq_varndims(ncid, varid, &var.ndims) );
	 var.dims = (int *) emalloc((var.ndims + 1) * sizeof(int));
	 NC_CHECK( nc_inq_var(ncid, varid, var.name, &var.type, 0,
			      var.dims, &var.natts) );
	 var.tinfo = get_typeinfo(var.type);

	 /* If coords-only option specified, don't get data for
	  * non-coordinate vars */
	 if (specp->coord_vals && !iscoordvar(ncid,varid)) {
	    continue;
	 }

	 /* Don't get data for record variables if no records have
	  * been written yet */
	 if (isrecvar(ncid, varid) && dims[xdimid].size == 0) {
	    continue;
	 }
		
	 /* Collect variable's dim sizes */
	 if (vdims) {
	     free(vdims);
	     vdims = 0;
	 }
	 vdims = (size_t *) emalloc((var.ndims + 1) * sizeof(size_t));
	 for (id = 0; id < var.ndims; id++)
	     vdims[id] = dims[var.dims[id]].size;
	 for (id = 0; id < var.ndims; id++)
	    vdims[id] = dims[var.dims[id]].size;
	 var.has_fillval = 1; /* by default, but turn off for bytes */
	    
	 /* get _FillValue attribute */
	 nc_status = nc_inq_att(ncid,varid,_FillValue,&att.type,&att.len);
	 fillvalp = emalloc(var.tinfo->size);
	 if(nc_status == NC_NOERR &&
	    att.type == var.type && att.len == 1) {
	     NC_CHECK(nc_get_att(ncid, varid, _FillValue, fillvalp));
	 } else {
	     switch (var.type) {
	     case NC_BYTE:
		 /* don't do default fill-values for bytes, too risky */
		 var.has_fillval = 0;
		 break;
	     case NC_CHAR:
		 *(char *)fillvalp = NC_FILL_CHAR;
		 break;
	     case NC_SHORT:
		 *(short *)fillvalp = NC_FILL_SHORT;
		 break;
	     case NC_INT:
		 *(int *)fillvalp = NC_FILL_INT;
		 break;
	     case NC_FLOAT:
		 *(float *)fillvalp = NC_FILL_FLOAT;
		 break;
	     case NC_DOUBLE:
		 *(double *)fillvalp = NC_FILL_DOUBLE;
		 break;
	     default:
		 break;
	     }
	 }
	 var.fillvalp = fillvalp;

	 /* printf format used to print each value */
	 var.fmt = get_fmt(ncid, varid, var.type);
	 set_tostring_func(&var);
	 if (vardata(&var, vdims, ncid, varid, specp) == -1) {
	    error("can't output data for variable %s", var.name);
	    NC_CHECK(
	       nc_close(ncid) );
	    if (vlist)
	       free(vlist);
	    return;
	 }
      }
#endif /* USE_NETCDF4 */
      if (vdims) {
	  free(vdims);
	  vdims = 0;
      }
   }
    
#ifdef USE_NETCDF4
   /* For netCDF-4 compiles, check to see if the file has any
    * groups. If it does, this function is called recursively on each
    * of them. */
   {
      int g, numgrps, *ncids;
      char group_name[NC_MAX_NAME + 1];

      /* Only netCDF-4 files have groups. */
      if (kind == NC_FORMAT_NETCDF4)
      {
	 /* See how many groups there are. */
	  NC_CHECK( nc_status = nc_inq_grps(ncid, &numgrps, NULL) );
	 
	 /* Allocate memory to hold the list of group ids. */
	 ncids = emalloc(numgrps * sizeof(int));
	 
	 /* Get the list of group ids. */
	 NC_CHECK( nc_inq_grps(ncid, NULL, ncids) );
	 
	 /* Call this function for each group. */
	 for (g = 0; g < numgrps; g++)
	 {
	    NC_CHECK( nc_inq_grpname(ncids[g], group_name) );
	    printf ("\n");
	    indent_out();
/* 	    printf ("group: %s {\n", group_name); */
	    printf ("group: ");
	    print_name (group_name);
	    printf (" {\n");
	    indent_more();
	    do_ncdump_rec(ncids[g], NULL, specp);
	    indent_out();
/* 	    printf ("} // group %s\n", group_name); */
	    printf ("} // group ");
	    print_name (group_name);
	    printf ("\n");
            indent_less();
	 }
	 
	 free(ncids);
      }
   }
#endif /* USE_NETCDF4 */

   if (vlist)
      free(vlist);
   if (dims)
      free(dims);
}


static void
do_ncdump(int ncid, const char *path, fspec_t* specp)
{
   char* esc_specname;
   /* output initial line */
   indent_init();
   indent_out();
   esc_specname=escaped_name(specp->name);
   printf ("netcdf %s {\n", esc_specname);
   free(esc_specname);
   do_ncdump_rec(ncid, path, specp);
   indent_out();
   printf ("}\n");
   NC_CHECK( nc_close(ncid) );
}


static void
do_ncdumpx(int ncid, const char *path, fspec_t* specp)
{
    int ndims;			/* number of dimensions */
    int nvars;			/* number of variables */
    int ngatts;			/* number of global attributes */
    int xdimid;			/* id of unlimited dimension */
    int dimid;			/* dimension id */
    int varid;			/* variable id */
    ncdim_t *dims;		/* dimensions */
    ncvar_t var;		/* variable */
    int ia;			/* attribute number */
    int iv;			/* variable number */
    vnode* vlist = 0;		/* list for vars specified with -v option */

    /*
     * If any vars were specified with -v option, get list of associated
     * variable ids
     */
    if (specp->nlvars > 0) {
	vlist = newvlist();	/* list for vars specified with -v option */
	for (iv=0; iv < specp->nlvars; iv++) {
	    NC_CHECK( nc_inq_varid(ncid, specp->lvars[iv], &varid) );
	    varadd(vlist, varid);
	}
    }

    /* output initial line */
    pr_initx(ncid, path);

    /*
     * get number of dimensions, number of variables, number of global
     * atts, and dimension id of unlimited dimension, if any
     */
    /* TODO: print names witth XML-ish escapes fopr special chars */
    NC_CHECK( nc_inq(ncid, &ndims, &nvars, &ngatts, &xdimid) );
    /* get dimension info */
    dims = (ncdim_t *) emalloc((ndims + 1) * sizeof(ncdim_t));
    for (dimid = 0; dimid < ndims; dimid++) {
	NC_CHECK( nc_inq_dim(ncid, dimid, dims[dimid].name, &dims[dimid].size) );
	if (dimid == xdimid)
  	  printf("  <dimension name=\"%s\" length=\"%d\" isUnlimited=\"true\" />\n", 
		 dims[dimid].name, (int)dims[dimid].size);
	else
	  printf ("  <dimension name=\"%s\" length=\"%d\" />\n", 
		  dims[dimid].name, (int)dims[dimid].size);
    }

    /* get global attributes */
    for (ia = 0; ia < ngatts; ia++)
	pr_attx(ncid, NC_GLOBAL, ia); /* print ia-th global attribute */

    /* get variable info, with variable attributes */
    for (varid = 0; varid < nvars; varid++) {
	NC_CHECK( nc_inq_varndims(ncid, varid, &var.ndims) );
	var.dims = (int *) emalloc((var.ndims + 1) * sizeof(int));
	NC_CHECK( nc_inq_var(ncid, varid, var.name, &var.type, 0,
			     var.dims, &var.natts) );
	printf ("  <variable name=\"%s\"", var.name);
	pr_shape(&var, dims);

	/* handle one-line variable elements that aren't containers
	   for attributes or data values, since they need to be
	   rendered as <variable ... /> instead of <variable ..>
	   ... </variable> */
	if (var.natts == 0) {
	    if (
		/* header-only specified */
		(specp->header_only) ||
		/* list of variables specified and this variable not in list */
		(specp->nlvars > 0 && !varmember(vlist, varid))	||
		/* coordinate vars only and this is not a coordinate variable */
		(specp->coord_vals && !iscoordvar(ncid, varid)) ||
		/* this is a record variable, but no records have been written */
		(isrecvar(ncid,varid) && dims[xdimid].size == 0)
		) {
		printf (" type=\"%s\" />\n", prim_type_name(var.type));
		continue;
	    }
	}

	/* else nest attributes values, data values in <variable> ... </variable> */
	printf (" type=\"%s\">\n", prim_type_name(var.type));

	/* get variable attributes */
	for (ia = 0; ia < var.natts; ia++) {
	    pr_attx(ncid, varid, ia); /* print ia-th attribute */
	}
	printf ("  </variable>\n");
    }
    
    printf ("</netcdf>\n");
    NC_CHECK(
	nc_close(ncid) );
    if (vlist)
	free(vlist);
    if(dims)
	free(dims);
}


static void
make_lvars(char *optarg, fspec_t* fspecp)
{
    char *cp = optarg;
    int nvars = 1;
    char ** cpp;

    /* compute number of variable names in comma-delimited list */
    fspecp->nlvars = 1;
    while (*cp++)
      if (*cp == ',')
 	nvars++;

    fspecp->lvars = (char **) emalloc(nvars * sizeof(char*));

    cpp = fspecp->lvars;
    /* copy variable names into list */
    for (cp = strtok(optarg, ",");
	 cp != NULL;
	 cp = strtok((char *) NULL, ",")) {
	size_t bufsiz = strlen(cp) + 1;
	
	*cpp = (char *) emalloc(bufsiz);
	strncpy(*cpp, cp, bufsiz);
	cpp++;
    }
    fspecp->nlvars = nvars;
}


/*
 * Extract the significant-digits specifiers from the (deprecated and
 * undocumented) -d argument on the command-line and update the
 * default data formats appropriately.  This only exists because an
 * old version of ncdump supported the "-d" flag which did not
 * override the C_format attributes (if any).
 */
static void
set_sigdigs(const char *optarg)
{
    char *ptr1 = 0;
    char *ptr2 = 0;
    int flt_digits = FLT_DIGITS; /* default floating-point digits */
    int dbl_digits = DBL_DIGITS; /* default double-precision digits */

    if (optarg != 0 && (int) strlen(optarg) > 0 && optarg[0] != ',')
        flt_digits = (int)strtol(optarg, &ptr1, 10);

    if (flt_digits < 1 || flt_digits > 20) {
	error("unreasonable value for float significant digits: %d",
	      flt_digits);
    }
    if (*ptr1 == ',')
      dbl_digits = (int)strtol(ptr1+1, &ptr2, 10);
    if (ptr2 == ptr1+1 || dbl_digits < 1 || dbl_digits > 20) {
	error("unreasonable value for double significant digits: %d",
	      dbl_digits);
    }
    set_formats(flt_digits, dbl_digits);
}


/*
 * Extract the significant-digits specifiers from the -p argument on the
 * command-line, set flags so we can override C_format attributes (if any),
 * and update the default data formats appropriately.
 */
static void
set_precision(const char *optarg)
{
    char *ptr1 = 0;
    char *ptr2 = 0;
    int flt_digits = FLT_DIGITS;	/* default floating-point digits */
    int dbl_digits = DBL_DIGITS;	/* default double-precision digits */

    if (optarg != 0 && (int) strlen(optarg) > 0 && optarg[0] != ',') {
        flt_digits = (int)strtol(optarg, &ptr1, 10);
	float_precision_specified = 1;
    }

    if (flt_digits < 1 || flt_digits > 20) {
	error("unreasonable value for float significant digits: %d",
	      flt_digits);
    }
    if (*ptr1 == ',') {
	dbl_digits = (int) strtol(ptr1+1, &ptr2, 10);
	double_precision_specified = 1;
    }
    if (ptr2 == ptr1+1 || dbl_digits < 1 || dbl_digits > 20) {
	error("unreasonable value for double significant digits: %d",
	      dbl_digits);
    }
    set_formats(flt_digits, dbl_digits);
}


int
main(int argc, char *argv[])
{
    extern int optind;
    extern int opterr;
    extern char *optarg;
    static fspec_t fspec =	/* defaults, overridden on command line */
      {
	  0,			/* construct netcdf name from file name */
	  false,		/* print header info only, no data? */
	  false,		/* just print coord vars? */
	  false,		/* brief  comments in data section? */
	  false,		/* full annotations in data section?  */
	  LANG_C,		/* language conventions for indices */
	  0,			/* if -v specified, number of variables */
	  0			/* if -v specified, list of variable names */
	  };
    int c;
    int i;
    int max_len = 80;		/* default maximum line length */
    int nameopt = 0;
    boolean xml_out = false;    /* if true, output NcML instead of CDL */
    boolean kind_out = false;	/* if true, just output kind of netCDF file */

#ifdef USE_PARALLEL
   MPI_Init(&argc, &argv);
#endif
    opterr = 1;
    progname = argv[0];
    set_formats(FLT_DIGITS, DBL_DIGITS); /* default for float, double data */

    /* If the user called ncdump without arguments, print the usage
     * message and return peacefully. */
    if (argc <= 1)
    {
       usage();
#ifdef vms
    exit(EXIT_SUCCESS);
#else
    return EXIT_SUCCESS;
#endif
    }

    while ((c = getopt(argc, argv, "b:cf:hkl:n:v:d:p:x")) != EOF)
      switch(c) {
	case 'h':		/* dump header only, no data */
	  fspec.header_only = true;
	  break;
	case 'c':		/* header, data only for coordinate dims */
	  fspec.coord_vals = true;
	  break;
	case 'n':		/*
				 * provide different name than derived from
				 * file name
				 */
	  fspec.name = optarg;
	  nameopt = 1;
	  break;
	case 'b':		/* brief comments in data section */
	  fspec.brief_data_cmnts = true;
	  switch (tolower(optarg[0])) {
	    case 'c':
	      fspec.data_lang = LANG_C;
	      break;
	    case 'f':
	      fspec.data_lang = LANG_F;
	      break;
	    default:
	      error("invalid value for -b option: %s", optarg);
	  }
	  break;
	case 'f':		/* full comments in data section */
	  fspec.full_data_cmnts = true;
	  switch (tolower(optarg[0])) {
	    case 'c':
	      fspec.data_lang = LANG_C;
	      break;
	    case 'f':
	      fspec.data_lang = LANG_F;
	      break;
	    default:
	      error("invalid value for -f option: %s", optarg);
	  }
	  break;
	case 'l':		/* maximum line length */
	  max_len = (int) strtol(optarg, 0, 0);
	  if (max_len < 10) {
	      error("unreasonably small line length specified: %d", max_len);
	  }
	  break;
	case 'v':		/* variable names */
	  /* make list of names of variables specified */
	  make_lvars (optarg, &fspec);
	  break;
	case 'd':		/* specify precision for floats (deprecated, undocumented) */
	  set_sigdigs(optarg);
	  break;
	case 'p':		/* specify precision for floats, overrides attribute specs */
	  set_precision(optarg);
	  break;
        case 'x':		/* XML output (NcML) */
	  xml_out = true;
	  break;
      case 'k':			/* just output what kind of netCDF file */
	  kind_out = true;
	  break;
      case '?':
	  usage();
	  return 0;
      }

    set_max_len(max_len);
    
    argc -= optind;
    argv += optind;

    /* If no file arguments left or more than one, print usage message. */
    if (argc != 1)
    {
       usage();
       return 0;
    }

    i = 0;

    init_epsilons();

    {		
	char *path = argv[i];
        if (!nameopt) 
	    fspec.name = name_path(path);
	if (argc > 0) {
	    int ncid, nc_status;
	    nc_status = nc_open(path, NC_NOWRITE, &ncid);
	    if (nc_status != NC_NOERR) {
		error("%s: %s", path, nc_strerror(nc_status));
	    }
	    if (kind_out) {
		do_nckind(ncid, path);
	    } else {
		/* Initialize list of types. */
		init_types(ncid);
		if (xml_out) {
		    do_ncdumpx(ncid, path, &fspec);
		} else {
		    do_ncdump(ncid, path, &fspec);
		}
	    }
	}
    }

#ifdef USE_PARALLEL
   MPI_Finalize();
#endif   

#ifdef vms
    exit(EXIT_SUCCESS);
#else
    return EXIT_SUCCESS;
#endif
}
