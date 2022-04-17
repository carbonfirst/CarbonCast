/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This tests reading and writing netcdf-4 files
   
   $Id: tst_filerw.cpp,v 1.4 2007/06/06 20:26:42 ed Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

using namespace netCDF;
using namespace std;
#define FILE_NAME "tst_filerw.nc"

int main(void)
{
  cout<<"*** Testing tst_filerw ";
  try
    {
      NcFile f(FILE_NAME,NcFile::Replace);
      NcGroup *root = f.getRootGroup();
      NcDim *lat = root->addDim(string("lat"),3);
      NcDim *lon = root->addDim(string("lon"),5);
      NcGroup *g1 = root->addGroup(string("firstSubGroup"));
     
    }
  catch(NcException c)
    {
      cout<<"FAILURE***"<<endl;
      c.what();
      return 1;
    }
  try
    {
      //      NcFile k(FILE_NAME,NcFile::ReadOnly);  // reading directly from the c++ 
                                                     //interface has not been implemented yet.
    }
  catch(NcException c)
    {
      cout<<"FAILURE***"<<endl;
      c.what();
      return 1;
    }
  
  cout<<"OK ***"<<endl;
  return 0;
}
