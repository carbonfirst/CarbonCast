/* This is part of the netCDF package.
   Copyright 2006 University Corporation for Atmospheric Research/Unidata.
   See COPYRIGHT file for conditions of use.

   This is an example which reads some 4D pressure and temperature
   values. The data file read by this program is produced by the
   companion program pres_temp_4D_wr.cpp. It is intended to illustrate
   the use of the netCDF C++ API.

   This program is part of the netCDF tutorial:
   http://www.unidata.ucar.edu/software/netcdf/docs/netcdf-tutorial

   Full documentation of the netCDF C++ API can be found at:
   http://www.unidata.ucar.edu/software/netcdf/docs/netcdf-cxx

   $Id: pres_temp_4D_rd.cpp,v 1.3 2007/07/30 00:18:22 forbes Exp $
*/

#include <iostream>
#include <netcdfcpp4.h>

using namespace std;
using namespace netCDF;

// We are writing 4D data, a 2 x 6 x 12 lvl-lat-lon grid, with 2
// timesteps of data.
static const int NLVL = 2;
static const int NLAT = 6;
static const int NLON = 12;
static const int NREC = 2;

// These are used to construct some example data. 
static const float SAMPLE_PRESSURE = 900.0;
static const float SAMPLE_TEMP = 9.0;
static const float START_LAT = 25.0;
static const float START_LON = -125.0; 


// Return this code to the OS in case of failure.
static const int NC_ERR = 2;

int main()
{
   // These arrays will store the latitude and longitude values.
   float lats[NLAT], lons[NLON];
   
   // These arrays will hold the data we will read in. We will only
   // need enough space to hold one timestep of data; one record.
   float pres_in[NLVL][NLAT][NLON];
   float temp_in[NLVL][NLAT][NLON];
   
   try
   {
   // Open the file.
   NcFile dataFile(string("pres_temp_4D.nc"), NcFile::ReadOnly);

   // Get pointers to the latitude and longitude variables.
   NcVar *latVar, *lonVar;
   if (!(latVar = dataFile.getVar(string("latitude"))))
      return NC_ERR;

   if (!(lonVar = dataFile.getVar(string("longitude"))))
      return NC_ERR;
// Get the lat/lon data from the file.
      if (!lonVar->get(lons, NLON))
      return NC_ERR;
	if(!latVar->get(lats,NLAT))
	return NC_ERR;

   cout<<"done with first two gets"<<endl;

   // Check the coordinate variable data. 
   for (int lat = 0; lat < NLAT; lat++)
       if (lats[lat] != START_LAT + 5. * lat)
	 return NC_ERR;

   for (int lon = 0; lon < NLON; lon++)
      if (lons[lon] != START_LON + 5. * lon)
 	return NC_ERR;
  
   // Get pointers to the pressure and temperature variables.
   NcVar *presVar, *tempVar;
   if (!(presVar = dataFile.getVar(string("pressure"))))
   	 return NC_ERR;

   if (!(tempVar  = dataFile.getVar(string("temperature"))))
      return NC_ERR;
  
   // Read the data. Since we know the contents of the file we know
   // that the data arrays in this program are the correct size to
   // hold one timestep. 
   for (int rec = 0; rec < NREC; rec++)
   {
      // Read the data one record at a time.
      if (!presVar->setCur(rec, 0, 0, 0))
	 return NC_ERR;
      if (!tempVar->setCur(rec, 0, 0, 0))
	 return NC_ERR;
 

      for (int lvl = 0; lvl < NLVL; lvl++)
	 for (int lat = 0; lat < NLAT; lat++)
	    for (int lon = 0; lon < NLON; lon++)
	       pres_in[lvl][lat][lon] = temp_in[lvl][lat][lon]= 0.5;

      // Get 1 record of NLVL by NLAT by NLON values for each variable.
      if (!presVar->get(&pres_in[0][0][0], 1, NLVL, NLAT, NLON))
	 return NC_ERR;

      if (!tempVar->get(&temp_in[0][0][0], 1, NLVL, NLAT, NLON))
	 	 return NC_ERR;
	   	   
      // Check the data. 
      int  i = 0;
      for (int lvl = 0; lvl < NLVL; lvl++)
	 for (int lat = 0; lat < NLAT; lat++)
	    for (int lon = 0; lon < NLON; lon++)
	       if (pres_in[lvl][lat][lon] != SAMPLE_PRESSURE + i || temp_in[lvl][lat][lon] != SAMPLE_TEMP + i++) 
		     return NC_ERR;
   } // next record 
       
   // The file is automatically closed by the destructor. This frees
   // up any internal netCDF resources associated with the file, and
   // flushes any buffers.

    cout << "*** SUCCESS reading example file pres_temp_4D.nc!" << endl;
   return 0;

   }
   catch(NcException e)
   {
      e.what();
      cout<<"FAILURE**************************"<<endl;
      return 1;
   }
  
}
