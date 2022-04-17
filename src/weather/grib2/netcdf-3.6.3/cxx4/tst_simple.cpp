/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This tests some simple cxx-4 stuff.
   
   $Id: tst_simple.cpp,v 1.11 2007/08/09 20:44:12 forbes Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

using namespace netCDF;
using namespace std;

#define FILE_NAME "tst_simple.nc"
#define NC_ERR 2

 NcAtomicType* ncNoType = new NcAtomicType(NC_UNSPECIFIED);; 
      NcAtomicType* ncByte = new NcAtomicType(NC_BYTE); 
      NcAtomicType* ncChar=new NcAtomicType(NC_CHAR);
      NcAtomicType* ncShort= new NcAtomicType(NC_SHORT); 
      NcAtomicType* ncInt= new NcAtomicType(NC_SHORT);
      NcAtomicType* ncFloat= new NcAtomicType(NC_FLOAT); 
      NcAtomicType* ncDouble= new NcAtomicType(NC_DOUBLE);
      NcAtomicType* ncUByte=new NcAtomicType(NC_UBYTE);
      NcAtomicType* ncUShort= new NcAtomicType(NC_USHORT);
      NcAtomicType* ncUInt=new NcAtomicType(NC_UINT);;
      NcAtomicType* ncInt64= new NcAtomicType(NC_INT64);
      NcAtomicType* ncUInt64= new NcAtomicType(NC_STRING);
      NcAtomicType* ncString= new NcAtomicType(NC_STRING);
      NcAtomicType* ncVLen=new NcAtomicType(NC_VLEN);
      NcAtomicType* ncOpaque= new NcAtomicType(NC_OPAQUE);
      NcAtomicType* ncEnum=new NcAtomicType(NC_ENUM);
      NcAtomicType* ncCompound=new NcAtomicType(NC_COMPOUND);

int main(void)
{

   cout << "*** Running some simple netCDF-4 tests." << endl;
   try
   {
      cout << "*** testing simple groups...";

      // Create a simple file and get root group.
      NcFile *f = new NcFile(FILE_NAME, NcFile::Replace);
      NcGroup *root = f->getRootGroup();

      // Create a dimension.
      NcDim *lat = root->addDim(string("lat"), 0);

      // Create a group. 
      string subgroup1 = "toddlers";
      NcGroup *toddlers = root->addGroup(subgroup1);

      // Create another group. 
      string subgroup2 = "preschoolers"; 
      NcGroup *preschoolers = root->addGroup(subgroup2);

      // Close the file.
      delete f;  // this isn't how you're supposed to close the file

      // Reopen the file and check. 
      NcFile *f1 = new NcFile(FILE_NAME,NcFile::ReadOnly);
      NcGroup *r1 = f1->getRootGroup();

      r1->getDim(string("lat"));
      
      NcGroup *t = r1->getGroup(subgroup1);

      // Close the file.
      delete f1;
      
      cout << "OK!" << endl;
   }
   catch(NcException c)
   {
      cout<<"Exception Occured"<<endl;
      c.what();
      cout << "*** FAILURE!" << endl;
      return 1;
   }

#define NLVL     2
#define NLAT     6
#define NLON     12
#define LVL_NAME "level"
#define LAT_NAME "latitude"
#define LON_NAME "longitude"
#define REC_NAME "time"
#define PRES_NAME     "pressure"
#define TEMP_NAME     "temperature"

   try
   {
      cout << "*** testing 4D file...";

      // Create the file.
      NcFile test(FILE_NAME, NcFile::Replace);

      // Define the dimensions.
      NcDim* lvlDim = test.addDim(LVL_NAME, NLVL);
      NcDim* latDim = test.addDim(LAT_NAME, NLAT);
      NcDim* lonDim = test.addDim(LON_NAME, NLON);
      NcDim* recDim = test.addDim(REC_NAME);  //adds an unlimited dimension
      
      NcVar* pressVar = test.addVar(PRES_NAME, ncFloat, recDim, lvlDim, 
				    latDim, lonDim);
      NcVar* tempVar = test.addVar(TEMP_NAME, ncFloat, recDim, lvlDim,
				   latDim, lonDim);
       
      cout << "OK!" << endl;
   }
   catch(NcException e)
   {
      e.what(); 
      cout << "*** FAILURE!" << endl;
      return 1;
   }

   cout << "*** SUCCESS! All simple netCDF-4 tests passed." << endl;
   return 0;
}
							      
