/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the Ncfile class
   
   $Id: ncatt.cpp,v 1.9 2007/07/31 18:51:41 forbes Exp $
*/

#include <netcdfcpp4.h>

namespace netCDF
{
   using namespace std;


   NcAtt::~NcAtt( void )
   {
 
   }
  
   string NcAtt:: getName( void ) const
   {
      return myName;
   }
  
   bool NcAtt:: isReadOnlyMode()
   {
      if(myGroup) // it's a group attribute
	 return myGroup->isReadOnlyMode();
      else// it's a varaible attribute
	 return myVariable->isReadOnlyMode();
   }

   NcType NcAtt:: getType( void ) const
   {
      int ret;
      int varid = NC_GLOBAL;
      nc_type type;
      if(myVariable)
	 varid = myVariable->getId();
      if((ret = nc_inq_atttype(myGroup->getNcId(),varid,myName.c_str(),&type)))
	 throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
      return (NcType) type;
   }
 
  
   bool NcAtt::rename( string newname )
   {
      int ret;
      if((ret = nc_rename_att (myNcId, myId,myName.c_str(), newname.c_str())))
	 throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
      myName= newname;
    
   }
   bool NcAtt::remove( void )
   {
      int ret;
      if((ret = nc_del_att(myNcId, myId, myName.c_str())))
	 throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
      return true;
   }
   
   bool NcAtt::isValid()
   {
      return valid;
   }
   string NcAtt::getValue() 
   {
      return myValue;
   }
   
}

