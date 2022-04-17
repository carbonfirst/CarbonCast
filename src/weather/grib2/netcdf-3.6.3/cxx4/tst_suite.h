#ifndef _TESTCASES_H_
#define _TESTCLASS_H_

#include "netcdfcpp4.h"

class TestSuite
{
 public:
  int  testFile(std::string fName,netCDF::NcFile::FileMode fMode);
  int testGroup();
  int  testAtt();
  int  testDim();
  int testVar();
  int  testExamples();
  int testTypes();
 private:
  int testsAttempted;
  int testsFailed;
};
#endif
