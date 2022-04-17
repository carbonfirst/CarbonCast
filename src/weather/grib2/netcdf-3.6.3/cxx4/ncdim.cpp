
/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the NcDim class
   
   $Id: ncdim.cpp,v 1.13 2007/07/31 15:37:56 forbes Exp $
*/
#include <config.h>
#include <netcdfcpp4.h>

namespace netCDF
{
  using namespace std;

  NcDim::NcDim(NcGroup *grp, string name, size_t j,int id)//(int parentId,string name, int size)
  {
    theGroup = grp;
    myNcId=grp->getId();  //was getNcId()
    myName=name;
    myId = id;
    int ret;
    if(!isReadOnlyMode())
      {
	if(!j)
	  { 
	
	    if((ret = nc_def_dim(myNcId,name.c_str(),NC_UNLIMITED,&myId)))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  }
	else
	  {
	    if((ret = nc_def_dim(myNcId,name.c_str(),j,&myId)))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  }
      }
      
  }


  NcDim::NcDim(NcGroup *grp, string name, size_t j)//(int parentId,string name, int size)
  {
    theGroup = grp;
    myNcId=grp->getId();  //was getNcId()
    myName=name;
    int ret;
    if(!isReadOnlyMode())
      {
	if(!j)
	  { 
	
	    if((ret = nc_def_dim(myNcId,name.c_str(),NC_UNLIMITED,&myId)))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  }
	else
	  {
	    if((ret = nc_def_dim(myNcId,name.c_str(),j,&myId)))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  }
      }
  }
  NcDim::NcDim(NcGroup *grp, string name)  //creates an unlimited dimnsion for the group
  {
    theGroup = grp;
    myNcId=grp->getId();  //was getNcId()
    myName=name;
    int ret;
    if(!isReadOnlyMode())
      if((ret = nc_def_dim(myNcId,name.c_str(),NC_UNLIMITED,&myId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
  }
   
  bool NcDim::isReadOnlyMode()   
  {
    return theGroup->isReadOnlyMode(); 
  }

  NcDim::~NcDim()
  {
  }
   
  bool NcDim::isUnlimited(void)const
  { //it's probably more appropriate to set a flag in the class when the dim is created
    int unlimdims[NC_MAX_DIMS];
    int temp,ret;
    if((ret = nc_inq_unlimdims(myNcId, &temp, unlimdims)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    if(temp>0)
      return true;
    return false;
  }
  
  size_t NcDim::getSize( void ) const
  {
    size_t sz;
    int ret;
    if((ret = nc_inq_dimlen(myNcId, myId, &sz)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    return sz;
    
  }
  
  bool NcDim::rename(string name)
  {
    int ret;
    if((ret = nc_rename_dim(myNcId, myId, name.c_str())))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    myName = name;
    return true;  //if it's gotten here it's successful
  }

  int NcDim::getId() const
  {
    return myId;
  }

  std::string NcDim::getName()const
  {
    return myName;
  }

  NcGroup* NcDim::getGroup()
  {
    return theGroup;
  }
  NcDim * NcDim::getDim()
  {
    return this;  
  }

}

