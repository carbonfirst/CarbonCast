/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.
   
   This tests netcdf-4 files.
   
   $Id: tst_file.cpp,v 1.10 2007/07/30 17:32:18 forbes Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

using namespace netCDF;
using namespace std;
#define FILE_NAME "tst_file.nc"
#define UNITS "UNITS:"

int main()
{
  cout<<"*** Testing tst_file ";
  int NLAT = 6;
  int NLON = 12;
  int NDIMS = 4;
  int NLVL = 2;
  int NREC = 2;
  
  /* These are used to construct some example data. */
  int SAMPLE_PRESSURE = 900;
  float SAMPLE_TEMP = 9.0;
  float START_LAT = 25.0;
  float START_LON = -125.0;
  
  
  /* We will write surface temperature and pressure fields. */
  float pres_out[NLAT][NLON];
  float pres_in[NLAT][NLON];
  float temp_out[NLAT][NLON];
  float temp_in[NLAT][NLON];
  float lats[NLAT], lons[NLON],lats_in[NLAT],lons_in[NLON];
  std::string  chararray []={"I"," hope"," this"," is"," stored "," properly" };
  std::string chararray_in[NLAT];
  int outInts[NLAT],outInts_in[NLAT];
      
  /* It's good practice for each netCDF variable to carry a "units"
   * attribute. */
  char pres_units[] = "hPa";
  char temp_units[] = "celsius";
      
  /* Loop indexes. */
  int lat, lon;
      
  /* Create some pretend data. If this wasn't an example program, we
   * would have some real data to write, for example, model
   * output. */
  for (lat = 0; lat < NLAT; lat++)
    {   
      lats[lat] = START_LAT + 5.*lat;
    }
  for(lat = 0; lat < NLAT; lat++)
    {  
      outInts[lat]= 450;
    }
  for (lon = 0; lon < NLON; lon++)
    {
      lons[lon] = START_LON + 5.*lon;
    }
  for (lat = 0; lat < NLAT; lat++)
    {
      for (lon = 0; lon < NLON; lon++)     
	{
	  pres_out[lat][lon] = SAMPLE_PRESSURE + (lon * NLAT + lat); 
	  temp_out[lat][lon] = SAMPLE_TEMP + .25 * (lon * NLAT + lat);
	}
    }
      
  // nc_set_log_level(3);
  try
    { 
      NcFile f(FILE_NAME,NcFile::Replace);
      NcGroup *root = f.getRootGroup();
      
      NcDim *latDim = root->addDim(string("lat"),NLAT);
      
      NcDim *lonDim = root->addDim(string("lon"),NLON);
      NcVar *latVar = root->addVar(string("latVar"),ncDouble,latDim);
 
      NcVar *lonVar = root->addVar(string("lonVar"),ncFloat,lonDim);
      NcVar *outIntsVar = root->addVar(string("outintsVar"),ncInt,latDim);
      NcVar *charArrVar = root->addVar(string("CharArray"),ncString,latDim);
      
      latVar->addAtt(string(UNITS),ncChar,string("degrees_north"));
      lonVar->addAtt(string(UNITS),ncChar,string("degrees_south"));
      
      outIntsVar->put(&outInts[0],NLAT,0,0,0,0); 
      charArrVar->put(&chararray[0],NLAT,0,0,0,0);
      
      latVar->put(&lats[0],NLAT,0,0,0,0);
      lonVar->put(&lons[0],NLON,0,0,0,0);
      
      NcVar *presVar = root->addVar(string("press"),ncFloat,latDim,lonDim);
      NcVar *tempVar = root->addVar(string("temp"),ncFloat,latDim,lonDim);
      presVar->addAtt(string("UNITS:"),ncChar,string(pres_units));
      tempVar->addAtt(string("UNITS:"),ncChar,string(temp_units));
      
      presVar->put(&pres_out[0][0],NLAT,NLON,0,0,0);
      tempVar->put(&temp_out[0][0],NLAT,NLON,0,0,0);
      
      {  //another scope for variables 
	NcGroup::varIterator variableItr;
	variableItr = root->beginVar();
	while(variableItr != root->endVar())
	  {
	    variableItr++;
	  }
	
	
	
	NcVar::attIterator varAttItr;
	varAttItr = latVar->beginAtt();
	while(varAttItr != latVar->endAtt())
	  {
	    varAttItr++;
	  }
	
      }
    }
  catch(NcException e)   
    {
      cout<<"FAILURE***"<<endl;
      e.what();
      return 1;
    }
  try
    {

      NcFile f1(FILE_NAME,NcFile::ReadOnly);

      NcGroup * root =f1.getRootGroup();

      NcGroup::dimIterator dimItr;            //get an iterator to move over the dimensions
      dimItr = root->beginDim();              //created in the file
	 
      // cout<<"the dimensions read from the file are"<<endl;
      while(dimItr != root->endDim())
	{
	  // cout<<dimItr->getName()<<" ";
	  dimItr++;
	 
	}

      // cout<<"the attributes read from the file are "<<endl;
      NcGroup::attIterator attItr;
      attItr= root->beginAtt();
      while(attItr !=root->endAtt())
	{
	  
	  // cout<<attItr->getName()<<": "<<attItr->getValue()<<" ";
	  attItr++;
	}
      //  cout<<"end of attributes"<<endl;
      //  cout<<"the variables in the root group are"<<endl;
      
	NcGroup::varIterator variableItr;
	NcVar::attIterator varAttItr;

	variableItr = root->beginVar();
	
	while(variableItr != root->endVar())
	  {
	    //  cout<< variableItr->getName()<<endl;
	    //  cout<<"my attributes are"<<endl;
	    	varAttItr = variableItr->beginAtt();
		while(varAttItr != variableItr->endAtt())
		  {
		    //	    cout<<varAttItr->getName()<<" "<<varAttItr->getValue()<<" ";
		    varAttItr++;
		  }
		//	cout<<"end of my attributes"<<endl;
		variableItr++;
	  }

    }
  catch(NcException e)   
    {
      cout<<"FAILURE***"<<endl;
      e.what();
      return 1;
    }
  
  cout<<" OK***"<<endl;
  return 0;
}

