/* This is part of the netCDF package.
   Copyright 2006 University Corporation for Atmospheric Research/Unidata.
   See COPYRIGHT file for conditions of use.

   This is a very simple example which writes a 2D array of
   sample data. To handle this in netCDF we create two shared
   dimensions, "X" and "Y", and a netCDF variable, called "data".

   This example demonstrates the netCDF C++ API. This is part of the
   netCDF tutorial:
   http://www.unidata.ucar.edu/software/netcdf/docs/netcdf-tutorial

   Full documentation of the netCDF C++ API can be found at:
   http://www.unidata.ucar.edu/software/netcdf/docs/netcdf-cxx

   $Id: sfc_pres_temp_wr.cpp,v 1.4 2007/07/30 00:18:22 forbes Exp $
*/

#include "netcdfcpp4.h"
//#include <iostream>
//#include <string.h>

using namespace std;
using namespace netCDF;
// This is the name of the data file we will create. 
#define FILE_NAME "sfc_pres_temp.nc"

// We are writing 2D data, a 6 x 12 lat-lon grid. We will need two
// netCDF dimensions.
int NDIMS = 2;
int NLAT = 6;
int NLON = 12;

// Names of things. 
string  PRES_NAME = "pressure";
string TEMP_NAME = "temperature";
string  UNITS = "units";
string  DEGREES_EAST = "degrees_east";
string DEGREES_NORTH = "degrees_north";
string LAT_NAME = "latitude";
string LON_NAME ="longitude";

// These are used to construct some example data. 
#define SAMPLE_PRESSURE 900
#define SAMPLE_TEMP     9.0
#define START_LAT       25.0
#define START_LON       -125.0

// Return this to OS if there is a failure.
#define NC_ERR 2

int main(void)
{
   // We will write surface temperature and pressure fields. 
   float presOut[NLAT][NLON];
   float tempOut[NLAT][NLON];
   float lats[NLAT];
   float lons[NLON];

   // In addition to the latitude and longitude dimensions, we will
   // also create latitude and longitude netCDF variables which will
   // hold the actual latitudes and longitudes. Since they hold data
   // about the coordinate system, the netCDF term for these is:
   // "coordinate variables."
   for(int lat = 0;lat < NLAT; lat++)
      lats[lat] = START_LAT + 5.*lat;
   
   for(int lon = 0; lon < NLON; lon++)
      lons[lon] = START_LON + 5.*lon;

   // Create some pretend data. If this wasn't an example program, we
   // would have some real data to write, for example, model
   // output. 
   for (int lat = 0; lat < NLAT; lat++)
      for(int lon = 0;lon < NLON; lon++)
      {
	 presOut[lat][lon] = SAMPLE_PRESSURE + (lon * NLAT + lat);
	 tempOut[lat][lon] = SAMPLE_TEMP + .25 * (lon * NLAT +lat);
      }
  
   try
   {
   
      // Create the file. The Replace parameter tells netCDF to overwrite
      // this file, if it already exists.
      NcFile sfc(FILE_NAME, NcFile::Replace);
   
      // Define the dimensions. NetCDF will hand back an ncDim object for
      // each.
      NcDim* latDim = sfc.addDim(LAT_NAME, NLAT); 
      NcDim* lonDim = sfc.addDim(LON_NAME, NLON);
       
      // Define coordinate netCDF variables. They will hold the
      // coordinate information, that is, the latitudes and
      // longitudes. An pointer to a NcVar object is returned for
      // each.
      NcVar *latVar = sfc.addVar(LAT_NAME, ncFloat, latDim);//creates variable
      NcVar *lonVar = sfc.addVar(LON_NAME, ncFloat, lonDim); 
    
      // Write the coordinate variable data. This will put the latitudes
      // and longitudes of our data grid into the netCDF file.
      latVar->put(&lats[0], NLAT, 0, 0, 0, 0);
      lonVar->put(&lons[0], NLON, 0, 0, 0, 0);
 
      // Define units attributes for coordinate vars. This attaches a
      // text attribute to each of the coordinate variables, containing
      // the units. Note that we are not writing a trailing NULL, just
      // "units", because the reading program may be fortran which does
      // not use null-terminated strings. In general it is up to the
      // reading C program to ensure that it puts null-terminators on
      // strings where necessary.
      lonVar->addAtt(UNITS,ncChar, DEGREES_EAST);
      latVar->addAtt(UNITS,ncChar ,DEGREES_NORTH);
    
      // Define the netCDF data variables.
      NcVar *presVar = sfc.addVar(PRES_NAME, ncFloat, latDim, lonDim);
      NcVar *tempVar = sfc.addVar(TEMP_NAME, ncFloat, latDim, lonDim);

      // Define units attributes for vars. 
      presVar->addAtt(UNITS,ncString, string("hPa"));
      tempVar->addAtt(UNITS,ncString ,string("celsius"));

      // Write the pretend data. This will write our surface pressure and
      // surface temperature data. The arrays of data are the same size
      // as the netCDF variables we have defined.
      presVar->put(&presOut[0][0], NLAT, NLON, 0, 0, 0);
      tempVar->put(&tempOut[0][0], NLAT, NLON, 0, 0, 0);
       
      // The file is automatically closed by the destructor. This frees
      // up any internal netCDF resources associated with the file, and
      // flushes any buffers.

      cout << "*** SUCCESS writing example file " << FILE_NAME << "!" << endl;
   }
   catch(NcException e)
   {
      e.what(); 
   }
   return 0;
}
