#include <netcdfcpp4.h>

namespace netCDF
{
  using namespace std;

  NcException::NcException(string complaint)
    {
      if(complaint.length()==0)
	{
	  message = "A netCDF exception has occured";
	}
      else
	{
	  message = complaint;	
	}
    }

  NcException::NcException(string complaint,char* file,int line,const char* func)
    {
      if(complaint.length()==0)
	{
	  message = "A netCDF exception has occured";
	}
      else
	{
	  message = complaint;
	  fileName = string(file);
	  lnumber = line;	
	  funcName = string(func);
	  // fileName = String(file);
	  
	}
    }
  
  NcException::NcException()
    {
      message = "A netCDF exception has occured";
    }

  NcException::NcException(char *complaint)
  {
    message=string(complaint);
  }
  
  NcException::~NcException()throw()
    {
//      cout<<"The NcException destructor was called"<<endl;
    }  // nothing to destroy
  
}
