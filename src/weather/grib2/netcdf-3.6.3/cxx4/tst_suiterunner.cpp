/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file runs the C++ api test suite
   
   $Id: tst_suiterunner.cpp,v 1.8 2007/07/30 17:32:18 forbes Exp $
*/
#include "tst_suite.h"
#include <iostream>
#include <string>

using namespace std;
using namespace netCDF;

int main(void)
{
  int i = 0;
  try
    {
      TestSuite firstTest;
     if(firstTest.testFile("tst_file.nc",netCDF::NcFile::Replace))
	return 1;
     if(firstTest.testAtt())
	return 1;
     if(firstTest.testDim())
	return 1;
     if(firstTest.testVar())
	return 1;
     if(firstTest.testGroup())
	return 1;
     if(firstTest.testExamples())
	return 1;
     if(firstTest.testTypes())
	return 1;
    if(firstTest.testVar())
	return 1;
    }
  catch(NcException e)
    {
       //   e.what();
      return 1;
    }
  return 0;
  
}
