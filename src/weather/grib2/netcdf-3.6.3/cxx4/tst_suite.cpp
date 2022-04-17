/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This test suite checks all the implemented features of the C++ API
   
   $Id: tst_suite.cpp,v 1.17 2007/07/31 19:44:41 forbes Exp $
*/

#include <config.h>
#include <tst_suite.h>


using namespace std;
using namespace netCDF;

int TestSuite::testFile(string fName, NcFile::FileMode fMode)
{
   string UNITS = "UNITS:";
  
   cout<<"*** Testing tst_file in tst_suite ";
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
      NcFile f("tst_file.nc",NcFile::Replace);
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

      //NcValues *ncvalues = presVar->getValues();
      
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
       
      NcFile f1("tst_file.nc",NcFile::ReadOnly);

      NcGroup * root =f1.getRootGroup();
       
      NcGroup::dimIterator dimItr;            //get an iterator to move over the dimensions
      dimItr = root->beginDim();              //created in the file
	 
      while(dimItr != root->endDim())
	 dimItr++;
	 
      NcGroup::attIterator attItr;
      attItr= root->beginAtt();
      while(attItr !=root->endAtt())
	 attItr++;
      
      NcGroup::varIterator variableItr;
      NcVar::attIterator varAttItr;

      variableItr = root->beginVar();
	
      while(variableItr != root->endVar())
      {
	 varAttItr = variableItr->beginAtt();
	 while(varAttItr != variableItr->endAtt())
	    varAttItr++;
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


int TestSuite::testAtt()
{
  
   char filename[] = "tstatt1.nc";
   int NLAT = 6;
   int NLON = 12;
   nc_type vr_type, t_type;   /* attribute types */
   size_t t_len; 
   int attId;
//byte myByte = -7;
   char myChar = 'J';
   short myShort = -127;
   int myInt = 20876;
   float myFloat = 23.985;
   double myDouble = 1.5673;
//unsigned byte myUByte = 7;
   unsigned short myUShort = 127;
   unsigned int myUInt = 8;
//int64, uint64
   string myString = "hello world";
//vlen
//opaque
//enum
//compound

 
   try
   {
      NcFile f(string(filename),NcFile::Replace);
      NcGroup *root = f.getRootGroup();
//    NcDim *lat = root->addDim(string("lat"),3);
      //  NcDim *lon = root->addDim(string("lon"),5);
      cout<<"about to begin adding attributes"<<endl;
      // root->addAtt("signedByte",ncByte,myByte);
      root->addAtt("signedChar",ncChar,myChar);
      root->addAtt("signedShort",ncShort,myShort);
      root->addAtt("signedInt",ncInt,myInt);
      root->addAtt("float",ncFloat,myFloat);
      root->addAtt("double",ncDouble,myDouble);
      //root->addAtt("unsignedByte",ncUByte,myUByte);  
      root->addAtt("unsignedShort",ncUShort,myUShort);
      root->addAtt("unsignedInt",ncUInt,myUInt);
      root->addAtt("string",ncString,myString);
    
//	root->addAtt(string("att1name"),ncChar,string("groupatt1"));
      //  root->addAtt(string("att2name"),ncChar,string("groupatt2"));
      
      //NcVar *latVar = root->addVar(string("latVar"),ncDouble,lat);
      
      //latVar->addAtt(string("location:"),ncChar,string("north"));
    
      // nc_inq_att (root->getId(), NC_GLOBAL, "att1name", &t_type, &t_len);
      // nc_inq_attid(root->getId(),latVar->getId(), "att1name", &attId);
            
      //NcVar::attIterator varAttItr;
      //varAttItr = latVar->beginAtt();
      //while(varAttItr != latVar->endAtt())
      //varAttItr++;


      NcVLenType *vlen;
      vlen=f.addVLenType("variableLengthType",ncChar);
      NcVar *vlenVar = root->addVar("variableLengthVariable",vlen);
      char stuff[35] = "hello world, I'm a vlen attribute";
      //vlenVar->addAtt("vlenatt",vlen,stuff);
   }
   catch(NcException e)
   {
      e.what(); 
      return 1;
   }
   return 0;
 
}

int TestSuite::testDim()
{
   bool fail = 0;  
 
/*    NcGroup::dimIterator dimItr;
    
dimItr = root->beginDim();
cout<<"the dimension names are"<<endl;
cout<<"***********************Now Testing Dimension Iterator*********************"<<endl;
    
while(dimItr != root->endDim())
{
cout<<" "<<dimItr->getName()<<" "<<endl;
dimItr++;
}
    
if(nc_open(filename,NC_NOWRITE, &myId) == NC_NOERR)
{
cout<<"about to call inq_dims"<<endl;
/*nc_inq_dimids(myId,&numDims,dimIds,1);  //get all the dimension id's for the file                                             
cout<<"got past inq_dims"<<endl;                                                                                                
for( int i=0; i<numDims; i++ )                                                                                                  
{                                                                                                                               
                                                                                                                                              
nc_inq_dim(myId,dimIds[i],name,&length);                                                                                      
                                                                                                                                              
if((name != dimItr->getName())||(length != dimItr->getSize()))                                                                
{                                                                                                                       
cout<<filename<<" does not contain the correct dimension information"<<endl;                                          
fail = 1;                                                                                                             
break;                                                                                                                
}                                                                                                                      
                                                                                                                                              
}*/
  
   if(fail)
   {
      //  cout<<"******************Testing Dimensions was Successful************************"<<endl;
      return 1;  
   }
   return 0;
}

int TestSuite::testGroup()
{
   bool fail = 0;
   char filename[] = "tsgroup.nc";
   int NLAT = 6;
   int NLON = 12;

   try
   {
      NcFile f(string(filename),NcFile::Replace);
      NcGroup *root = f.getRootGroup();
      NcDim *lat = root->addDim(string("lat"),3);
      NcDim *lon = root->addDim(string("lon"),5);
      
      string v1 = "var1";
      NcGroup *g0 = root->addGroup(string("Temp"));
      
                  
      NcDim *latDim = g0->addDim(string("lat"),NLAT);
      NcDim *lonDim = g0->addDim(string("lon"),NLON);
     
      NcGroup *g1 = g0->addGroup(string("North"));
      NcGroup *g2 = g0->addGroup(string("South"));
      NcGroup *g3 = g1->addGroup(string("USA"));
      NcGroup *g4 = g1->addGroup(string("Canada"));
      NcGroup *g5 = g2->addGroup(string("Venezuela"));
      NcGroup *g6 = g2->addGroup(string("Brazil"));
      NcGroup *g7 = g3->addGroup(string("Texas"));
      
      
      
      try//negative tests
      {
      
	 NcGroup *g0= root->addGroup(string("Temp")); //should cause an exception since this alreadexists
      
      }
      catch(NcException e)
      {
	 // e.what();   // commented out b/c this ie expected to fail
      }

      root->addAtt(string("att1name"),ncChar,string("groupatt1"));
      root->addAtt(string("att2name"),ncChar,string("groupatt2"));
      g0->addAtt(string("tempatt"),ncChar,string("tempatt1"));
      
      NcGroup::grpIterator groupIterator;
      groupIterator = g0->beginGrp();
      while(groupIterator != g0->endGrp())
      {
	 groupIterator++;
      }
      f.close();  //saves the file so it can be opened for reading        
      int myId;  //ncid of the file
      char name[NC_MAX_NAME+1]; //name read from file
      int numGrps;
      int grpIds[10];
      size_t length; //size of current dimension
      int format;   
      int numDims;

      if(nc_open(filename,NC_NOWRITE, &myId) == NC_NOERR)
      {
	 nc_inq_grps(myId,&numGrps,grpIds);
	     
	 int i=0;

	 nc_inq_grpname(grpIds[i],name);  //not sure if this works properly
	      
	 if(!strcmp(name,"North"))
	 {
	    fail = 1;
	    //break;
	 }	
	 i++;

	 nc_inq_grpname(grpIds[i],name);  //not sure if this works properly                                                                                                                                                                         

	 if(!strcmp(name,"South"))
	 {
	    fail = 1;
	 }

                
      }
   }
   catch(NcException e)   
   {
      e.what();
      return 1;
   }
   return 0;
}

int TestSuite::testVar()
{


   try
   {

      string FILE_NAME = "tst_vars.nc";
      int NDIMS = 4;
      int NLAT = 6;
      int NLON = 12;

      // Names of things. 
      string LAT_NAME = "latitude";
      string LON_NAME = "longitude";

      int  MAX_ATT_LEN = 80;
      // These are used to construct some example data. 
      float START_LAT = 25.0;
      float START_LON = -125.0;

      string  UNITS = "units";
      string  DEGREES_EAST =  "degrees_east";
      string  DEGREES_NORTH = "degrees_north";

      // For the units attributes. 
      string LAT_UNITS = "degrees_north";
      string LON_UNITS = "degrees_east";

      // Return this code to the OS in case of failure.
#define NC_ERR 2

  
      // We will write latitude and longitude fields. 
      float lats[NLAT],lons[NLON];

      // create some pretend data. If this wasn't an example program, we
      // would have some real data to write for example, model output.
      for (int lat = 0; lat < NLAT; lat++)
	 lats[lat] = START_LAT + 5. * lat;
      for (int lon = 0; lon < NLON; lon++)
	 lons[lon] = START_LON + 5. * lon;

      // Create the file.
      NcFile test(FILE_NAME, NcFile::Replace);

      // Define the dimensions. NetCDF will hand back an ncDim object for
      // each.
      NcDim* latDim = test.addDim(LAT_NAME, NLAT);
      NcDim* lonDim = test.addDim(LON_NAME, NLON);

   
      // Define the coordinate variables.
      NcVar* latVar = test.addVar(LAT_NAME, ncFloat, latDim);
      NcVar* lonVar = test.addVar(LON_NAME, ncFloat, lonDim);
       
      // Define units attributes for coordinate vars. This attaches a
      // text attribute to each of the coordinate variables, containing
      // the units.
      latVar->addAtt(UNITS,ncString, DEGREES_NORTH);
      lonVar->addAtt(UNITS,ncString, DEGREES_EAST);

      // Write the coordinate variable data to the file.
      latVar->put(lats, NLAT);
      lonVar->put(lons, NLON);

      NcValues *latVals = latVar->getValues();
      cout<<"toString returns lats: "<<latVals->toString()<<endl;
      cout<<"toChar returns "<<latVals->toChar(1)<<endl;
      cout<<"toShort returns "<<latVals->toShort(1)<<endl;
      cout<<"toInt returns "<<latVals->toInt(1)<<endl;
      cout<<"toLong returns "<<latVals->toLong(1)<<endl;

      latVals->print(cout);
      
      NcValues *lonVals = lonVar->getValues();
      cout<<"toString returns lats: "<<lonVals->toString()<<endl;
      lonVals->print(cout);
      
	
      cout<<"no segmentation fault thus far"<<endl;
 

      //test varaibles here
   }
   catch(NcException e)
   {
      e.what();
      return 1;
   }
   try
   {
      cout<<"should test adding a variable with more than 5 dimensions here"<<endl;
      // test creating a variable with more than 5 dimensions
   } 
   catch (NcException e)
   {
      e.what();
      return 1;
   }


 
   try  //write the file with float's b/c that's all NcValues can handle at the moment
    {  
       int NX = 6;
      int NY = 12;
       float dataOut[NX][NY];
       
  // Create some pretend data. If this wasn't an example program, we
  // would have some real data to write, for example, model output.
  for(int i = 0; i < NX; i++)
    for(int j = 0; j < NY; j++)
       dataOut[i][j] = i * NY + j;
 
  // The default behavior of the C++ API is to throw an exception i
  // an error occurs. A try catch block in necessary.
   
      // Create the file. The Replace parameter tells netCDF to overwrite
      // this file, if it already exists.
      string filename ="simples_xy.nc"; 
      NcFile dataFile(filename, NcFile::Replace);
      
      
      // When we create netCDF dimensions, we get back a pointer to an
      // NcDim for each one.
      NcDim* xDim = dataFile.addDim("x", NX);
      NcDim* yDim = dataFile.addDim("y", NY);
      
      // Define the variable. The type of the variable in this case is
      // ncInt (32-bit integer).
   NcVar *data = dataFile.addVar("data", ncFloat, xDim, yDim);
   
   // Write the pretend data to the file. Although netCDF supports
   // reading and writing subsets of data, in this case we write all
   // the data in one operation.
   data->put(&dataOut[0][0], NX, NY,0,0,0);
   
   // The file will be automatically close when the NcFile object goes
   // out of scope. This frees up any internal netCDF resources
   // associated with the file, and flushes any buffers.
   
   cout << "*** SUCCESS writing example file simples_xy.nc!" << endl;
    }
  catch(std::exception e)
    {e.what();}


   try
   {
      int NX = 6;
      int NY = 12;

// Return this in event of a problem.
      // int NC_ERR = 2;
      // This is the array we will read.
      float dataIn[NX][NY]; 

      // Open the file. The ReadOnly parameter tells netCDF we want
      // read-only access to the file.
      NcFile dataFile("simples_xy.nc", NcFile::ReadOnly);

      // Retrieve the variable named "data"
      NcVar *data = dataFile.getVar("data");
      //call getType on data

      // Read all the values from the "data" variable into memory. 
      data->get(&dataIn[0][0], NX, NY);
      // Check the values. 
      for (int i = 0; i < NX; i++)
	 for (int j = 0; j < NY; j++)
	    if (dataIn[i][j] != i * NY + j)
	       return 1;
	    
      NcValues* dataVar= data->getValues();
      cout<<dataVar->toString()<<endl;;
      dataVar->print(cout);
    
   }
   catch(NcException e)
   {
      e.what();
      return 1;
   }
      cout<<"***************** Testing Variables was successful *****************"<<endl;
      return 0;
}


int TestSuite::testExamples()
{

#define FILE_NAME "pres_temp_4D.nc"

   // We are writing 4D data, a 2 x 6 x 12 lvl-lat-lon grid, with 2
   // timesteps of data.
#define NDIMS    4
#define NLVL     2
#define NLAT     6
#define NLON     12
#define NREC     2

   // Names of things. 
#define LVL_NAME "level"
#define LAT_NAME "latitude"
#define LON_NAME "longitude"
#define REC_NAME "time"
#define PRES_NAME     "pressure"
#define TEMP_NAME     "temperature"
#define MAX_ATT_LEN  80
   // These are used to construct some example data. 
#define SAMPLE_PRESSURE 900
#define SAMPLE_TEMP     9.0
#define START_LAT       25.0
#define START_LON       -125.0


   string  UNITS = "units";
   string  DEGREES_EAST =  "degrees_east";
   string  DEGREES_NORTH = "degrees_north";


   // For the units attributes. 
   string PRES_UNITS = "hPa";
   string TEMP_UNITS = "celsius";
   string LAT_UNITS = "degrees_north";
   string LON_UNITS = "degrees_east";

   // Return this code to the OS in case of failure.
#define NC_ERR 2

  
   // We will write latitude and longitude fields. 
   float lats[NLAT],lons[NLON];

   // Program variables to hold the data we will write out. We will
   // only need enough space to hold one timestep of data; one record.
   float pres_out[NLVL][NLAT][NLON];
   float temp_out[NLVL][NLAT][NLON];

   int i=0;  //used in the data generation loop
  
   // create some pretend data. If this wasn't an example program, we
   // would have some real data to write for example, model output.
   for (int lat = 0; lat < NLAT; lat++)
      lats[lat] = START_LAT + 5. * lat;
   for (int lon = 0; lon < NLON; lon++)
      lons[lon] = START_LON + 5. * lon;

   for (int lvl = 0; lvl < NLVL; lvl++)
      for (int lat = 0; lat < NLAT; lat++)
	 for (int lon = 0; lon < NLON; lon++)
	 {
	    pres_out[lvl][lat][lon] = SAMPLE_PRESSURE + i;
	    temp_out[lvl][lat][lon]  = SAMPLE_TEMP + i++;
	 }
 
   try
   {
    
   
      // Create the file.
      NcFile test(FILE_NAME, NcFile::Replace);

      // Define the dimensions. NetCDF will hand back an ncDim object for
      // each.
      NcDim* lvlDim = test.addDim(LVL_NAME, NLVL);
      NcDim* latDim = test.addDim(LAT_NAME, NLAT);
      NcDim* lonDim = test.addDim(LON_NAME, NLON);
      NcDim* recDim = test.addDim(REC_NAME);  //adds an unlimited dimension
       
      // Define the coordinate variables.
      NcVar* latVar = test.addVar(LAT_NAME, ncFloat, latDim);
      NcVar* lonVar = test.addVar(LON_NAME, ncFloat, lonDim);
       
      // Define units attributes for coordinate vars. This attaches a
      // text attribute to each of the coordinate variables, containing
      // the units.
      latVar->addAtt(UNITS,ncChar, DEGREES_NORTH);
      lonVar->addAtt(UNITS,ncChar, DEGREES_EAST);
       
      // Define the netCDF variables for the pressure and temperature
      // data.
      NcVar* pressVar = test.addVar(PRES_NAME, ncFloat, recDim, lvlDim, 
				    latDim, lonDim);
      NcVar* tempVar = test.addVar(TEMP_NAME, ncFloat, recDim, lvlDim,
				   latDim, lonDim);
       
      // Define units attributes for coordinate vars. This attaches a
      // text attribute to each of the coordinate variables, containing
      // the units.
      pressVar->addAtt(UNITS,ncChar, PRES_UNITS);
      tempVar->addAtt(UNITS,ncChar ,TEMP_UNITS);

      // Write the coordinate variable data to the file.
      latVar->put(lats, NLAT);
      lonVar->put(lons, NLON);
            
      // Write the pretend data. This will write our surface pressure and
      // surface temperature data. The arrays only hold one timestep
      // worth of data. We will just rewrite the same data for each
      // timestep. In a real application, the data would change between
      // timesteps.

      for (int rec = 0; rec < NREC; rec++)
      {
	 pressVar->putRec(&pres_out[0][0][0], rec);
	 tempVar->putRec(&temp_out[0][0][0], rec);
      }

      //NcValues * pressVals = pressVar->getValues();
      //pressVals->print(cout);

      // The file is automatically closed by the destructor. This frees
      // up any internal netCDF resources associated with the file, and
      // flushes any buffers.
   
      cout << "*** SUCCESS writing example file " << FILE_NAME << "!" << endl;
   }
   catch(NcException e)
   {
      e.what(); 
      return 1;
   }
   return 0;
 
}


int TestSuite::testTypes()
{
   try
   {
      NcFile f("tst_types.nc",NcFile::Replace);
      NcEnumType *state;
      NcGroup * root;
      root = f.getRootGroup();
 
      state =f.addEnumType("state");
      state->addMember("sitting",10);
      state->addMember("standing",11);
      state->addMember("walking",12);
      state->addMember("running",13);
      enum estuff{sitting =10, standing =11, walking =12,running = 13};
      estuff s;
      s = standing;
      
      NcVar *var = root->addVar("enumVar",state);
      var->put(&s);// how do I store and variable that is of enumaration type
      cout<<" done with enum stuff*****************************************************"<<endl;
          

      NcCompoundType *myStruct;

      struct s1
      {
	    int i1;
	    int i2;
      };
      
      myStruct = f.addCompoundType("basicCompoundType",sizeof(s1));
      myStruct->addMember("i1",NC_INT);
      myStruct->addMember("i2",NC_INT);
      
      
      s1 tempStruct;
      tempStruct.i1= 23;
      tempStruct.i2= 15;
      NcVar *var1= root->addVar("basicCompoundVariable",myStruct);
      var1->put(&tempStruct);
      //var1->addAtt("basicCompoundAtt",myStruct,&tempStruct);
      cout<<"done with basic compound stuff *********************************************"<<endl;
      
      struct cs
      {
	    s1 s;
	    int j;
	    string k;
      };
      
      NcCompoundType * compStruct;
      compStruct= f.addCompoundType("mediumCompoundType",sizeof(cs));
      
      compStruct->addMember("s",myStruct);
      compStruct->addMember("j",NC_INT);
      compStruct->addMember("k",NC_STRING);
	
      cs struct2;
      struct2.s = tempStruct;
      struct2.j =15;
      struct2.k = "it works";
      NcVar *var2= root->addVar("mediumCompoundVariable",compStruct);
      var2->put(&struct2);
     
      cout<<"*******************done with medium compund stuff*******************"<<endl;
      
      struct cs3
      {
	    s1 a;
	    s1 b;
	    estuff k;
	    int i;
      };
      
      NcCompoundType *compStruct2 = f.addCompoundType("complexCompoundType",sizeof(cs3));
      compStruct2->addMember("a",myStruct);
      compStruct2->addMember("b",myStruct);
      compStruct2->addMember("k",state);
      compStruct2->addMember("i",NC_INT);
      cs3 comps2v;
      comps2v.a = tempStruct;
      comps2v.b =  tempStruct;
      comps2v.k = s;
      comps2v.i = 1985;
      NcVar *var3= root->addVar("complexCompoundVariable",compStruct2);
      var3->put(&comps2v);
      cout<<"*********************done with complex compound stuff***************************************"<<endl;

      cout<<"****************************now doing variable length stuff****************************"<<endl;
      nc_vlen_t data1[3];
      int *phoney;
      
 
/* Create phoney data. */
      for (int i=0; i<3; i++)
      {
	 if (!(phoney = new int[i+1]))
	    return NC_ENOMEM;
	 for (int j=0; j<i+1; j++)
	    phoney[j] = -99;
	 data1[i].p = phoney;
	 data1[i].len = i+1;
      }

      NcVLenType *vlen;
      vlen=f.addVLenType("variableLengthType",ncInt);
//NcVar *vlenVar = root->addVar("variableLengthVariable",vlen);
      string stuff = "hello world";
//vlenVar->addAtt("vlenatt",vlen,data1);

      cout<<"about to call put for variable vlenvar"<<endl;

//vlenVar->put(&data1);
      cout<<"I just called put for the variable lenght data. I'm in the tst_...cpp file, hopefully it works"<<endl;



      cout<<"*********************now dealing with opaque stuff*************************"<<endl;
      unsigned char data[5][5];
      for(int i = 0;i < 5; i++)
      {
	 for(int j =0; j<5; j++)
	 {
	    data[i][j]= 'a';
	 }
      }

      NcOpaqueType *opaque;
      opaque = f.addOpaqueType("opaqueType",sizeof(data));
      NcVar *ovar = root->addVar("opaqueVar",opaque);
//ovar->put(&data);
      cout<<"********************done with opaque stuff ******************************"<<endl;
	
   }
   catch(NcException e)
   {
      e.what();
      return 1;
   }

   try
   {
      cout<<"I'm going to try reading now"<<endl;
      NcFile f("tst_types.nc",NcFile::ReadOnly);
      cout<<"hopefully all the stuff has been read correctly"<<endl;
   }
   catch(NcException e)
   {
      e.what();
      return 1;
   }
   return 0;
}
