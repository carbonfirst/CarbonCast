/* 
   This is part of the netCDF-4 package. Copyright 2007 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the Ncfile class
   
   $Id: ncfile.cpp,v 1.24 2007/09/25 15:43:30 russ Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

namespace netCDF
{
  using namespace std;

  NcFile::NcFile(string path, FileMode fMode, size_t* chunkSizePtr, 
		 size_t initialSize, FileFormat fFormat)
  {
    myMode  = NC_NOWRITE;
    myFillMode = Fill;
    isOpen = false;
    inReadOnlyMode = false;
    
    // If the user wants a 64-bit offset format, set that flag.
    if (fFormat == Offset64Bits)
      myMode |= NC_64BIT_OFFSET;
#ifdef USE_NETCDF4
    else if (fFormat == Netcdf4)
      myMode |= NC_NETCDF4;
    else if (fFormat == Netcdf4Classic)
      myMode |= NC_NETCDF4|NC_CLASSIC_MODEL;
#endif
    
    switch (fMode) 
      {
      case Write:
	myMode |= NC_WRITE;
	/*FALLTHRU*/
      case ReadOnly:
	if(nc_open(path.c_str(), myMode, &myId)!=NC_NOERR)
	  throw NcException("Error opening file", __FILE__, __LINE__, __FUNCTION__);

	inDefineMode = false;
	isOpen = true;
	myRootGroup = new NcGroup(myId,this);
	break;
      case New:
	myMode |= NC_NOCLOBBER;
	/*FALLTHRU*/
      case Replace:
	{
	  if(nc_create(path.c_str(), myMode, &myId) != NC_NOERR)
	    throw NcException("Error creating file", __FILE__, __LINE__, __FUNCTION__);

	  inDefineMode = true;
	  isOpen = true;
	  myRootGroup = new NcGroup(myId,this);
	}
	break;
      default:
	myId = NC_EBADID;   //not sure if this is the corrrect assignment
	inDefineMode = false;
	//not open
      }
  }
  

  NcFile::NcFile( string path, FileMode fMode)
  {
    //cout<<"file constructor called"<<endl;
    FileFormat fFormat = Netcdf4;  // this may need to be changed later to accomodate non netcdf-4 files
    
    int ret;
    myMode  = NC_NOWRITE;
    inReadOnlyMode = false;

    myFillMode = Fill;
    //if(fMode != ReadOnly)
    // {
    myMode |= NC_NETCDF4;
    //}
    /* else
       {
       myMode|=NC_CLASSIC_MODEL;//HOPEFULLY THIS WILL WORK FOR NOW 
       }*/
    // If the user wants a 64-bit offset format, set that flag.
    if (fFormat == Offset64Bits)
      myMode |= NC_64BIT_OFFSET;
#ifdef USE_NETCDF4
    else if (fFormat == Netcdf4)
      myMode |= NC_NETCDF4;
    else if (fFormat == Netcdf4Classic)
      myMode |= NC_NETCDF4|NC_CLASSIC_MODEL;
#endif
    
    int format;
    switch (fMode) 
      {
      case Write:
	myMode |= NC_WRITE;  // not sure if this is correct
	/*fallthrough*/
      case ReadOnly:
	{
	  if(fMode == ReadOnly)
	    {
	      myMode  |= NC_NOWRITE;
	      myName = path;
	      inReadOnlyMode = true;
	    }

	  if(!(nc_open(path.c_str(), myMode, &myId)==NC_NOERR))
	    throw NcException("Error opening file",__FILE__,__LINE__,__FUNCTION__);
	    
	  inDefineMode = false;
	  isOpen = true;
	  myRootGroup = new NcGroup(myId,this);  // this creates the root group  
	    
	  if((ret = nc_inq_format(myId, &format)))// checks the files format 
	    throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	    
	  readGroups(myRootGroup,myId);

	  if(fMode == Write)
	    inReadOnlyMode = false;
	}
	break;
      case New:
	myMode |= NC_NOCLOBBER;
	/*FALLTHRU*/
      case Replace:
	{
	    
	  if(nc_create(path.c_str(),NC_NETCDF4,&myId)!=NC_NOERR)  //myMode was replaced by NC_NETCDF4  
	    {
	      throw NcException("Error creating file");
	    }
	    
	  inDefineMode = true; 
	  isOpen = true;
	  myRootGroup = new NcGroup(myId,this);
	  inReadOnlyMode = false;
	}
	break;
      default:
	myId = NC_EBADID;   //not sure if this is the corrrect assignment
	inDefineMode = false;
	//not open
      }
  }
  
  
  void   NcFile::readGroups(NcGroup *group,int id)
  {
    int ret;
    int dimCount,attCount,varCount,unlimDimCount =0; 
    
    int grpCount;
    nc_type xtype;
    if((ret = nc_inq_grps(id,&grpCount,NULL)))  //gets the number of subgroups
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

    if((ret = nc_inq(id,&dimCount,&varCount,&attCount,&unlimDimCount)))  // get num dimensions, variables, atts, and unlimdims
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

    readAttributes(group,attCount);  //read the attributes for this group
    readDimensions(group,dimCount);  //read the dimensions for this group
    readVariables(group,varCount);   //read teh variables for this group
     
    char gname[100];
    if(grpCount > 0)
      {
	int grpIds[grpCount];
	if((ret = nc_inq_grps(id,NULL,grpIds)))         //get a list of the sub group ids
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    
	NcGroup *tempGrp;  //assumption is made that they'll be give the same id as in the file when they are created here
     
	for(int i = 0; i < grpCount; i++)  //get the subgroup info
	  {
	    if((ret = nc_inq_grpname(grpIds[i],gname)))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	    tempGrp = myRootGroup->addGroup(gname,grpIds[i]);
	    readGroups(tempGrp,grpIds[i]);
	  }
      }
  }

    

  void NcFile::readDimensions(NcGroup *group, int dimCount)
  {
    int ret;  
    int dimIds[dimCount];
    if((ret = nc_inq_dimids(myId,&dimCount,dimIds,0)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	        
    char name[100];
    size_t dimLen;

    for(int i = 0; i < dimCount; i++)

      {
	if((ret = nc_inq_dim(myId,dimIds[i],name,&dimLen)))
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	group->addDim(string(name),dimLen,dimIds[i]);
      }
  }

  void NcFile::readAttributes(NcGroup *group, int attCount)
  {
    int ret;
    nc_type type;
    size_t len;
    char name[100];
      
   
    for(int i =0; i<attCount; i++)
      {
	if((ret = nc_inq_attname(group->getId(),NC_GLOBAL,i,name))) //get the name of the global attribute, using the old name array from dimstuff
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	size_t lenp;
	 
	if((ret = nc_inq_attlen(group->getId(),NC_GLOBAL,name,&lenp)))
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

	char attval[lenp +1]; 
	if((ret = nc_get_att(group->getId(),NC_GLOBAL,name,attval))) // name== units, attname == celcius  etc
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	attval[lenp] = 0;
	 
	group->addAtt(string(name),ncChar,string(attval));  //will need to be modified to read all types
      }
  }

  void NcFile::readAttributes(NcVar *var, int attCount)
  {
    int ret;
    nc_type type;
    size_t len;
    char name[100];
    size_t lenp =0;
    for(int i =0; i<attCount; i++)
      {
	if((ret = nc_inq_attname(var->getNcId(),var->getId(),i,name))) //get the name of the global attribute, using the old name array from dimstuff
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	
	if((ret = nc_inq_attlen(var->getNcId(),var->getId(),name,&lenp)))
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

	lenp =3;	
	
	char attval[lenp+1]; 
	if((ret = nc_get_att(var->getNcId(),var->getId(),name,attval))) // name== units, attname == celcius  etc
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	attval[lenp]= 0;

	//get att doeen't always get the correct value
	var->addAtt(string(name),ncChar,string(attval));//will need to be changed later to handle all types
      }
  }
   
   
  void NcFile::readVariables(NcGroup *group, int vCount)
  {
    //cout<<"about to read variables"<<endl;
    int ret;
    int varIds[vCount];
    if((ret = nc_inq_varids(group->getId(),0,varIds)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

    char name[100];
    nc_type type;
    int numDims;
    int dimIds[5];
    int numAtts;
    char dname[50];
    nc_type xtype;
      
    for(int i = 0;i < vCount; i++)
      {
	if((ret = nc_inq_var(group->getId(),varIds[i],name,&type,&numDims, dimIds,&numAtts)))
	  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	 	 
	if(type > NC_STRING) // you'd create the user defined type here
	  {
	    char cname[100];
	    size_t size;
	    size_t nfields;
	    nc_type base_nc_type;
	    int classp;
	      
    
	    if(ret =  nc_inq_user_type(group->getNcId(),type, cname, &size,&base_nc_type,&nfields,&classp))
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	     
	    switch(classp)
	      {
	      case NC_VLEN:
		{
		  NcVLenType *temp;
		  temp = new NcVLenType(myRootGroup,cname,(NcType)type);
		  myVLenTypes.insert(pair<string,NcVLenType*>(cname,temp)); 
		}
		break;
	      case NC_OPAQUE:
		{
		  NcOpaqueType *temp;
		  temp = new NcOpaqueType(myRootGroup,cname,size,type);
		  myOpaqueTypes.insert(pair<string,NcOpaqueType *>(cname,temp));
		}
		break;
	      case NC_ENUM:
		{
		  NcEnumType * temp;
		  temp = new NcEnumType(myRootGroup,cname,type);  //currently on only integers are support
		  myEnumTypes.insert(pair<string,NcEnumType*>(cname,temp)); 
		}
		break;
	      case NC_COMPOUND:
		{
		  NcCompoundType *temp;
		  temp = new NcCompoundType(myRootGroup, size, cname,type);
		  myCompoundTypes.insert(pair<string,NcCompoundType*>(cname,temp));
		}
		break;
	      default:
		cout<<"not a user defined type variable"<<endl;
		break;
	      }
		  
	    
	  }
	NcVar* var = new NcVar(group,name, (nc_type) type, numDims,&dimIds[0],varIds[i]);
	group->myVariables.insert(make_pair(name,var));  //keeps track of the variables that have been added
	
	readAttributes(var,numAtts); //hopefully this is the correct place
      }
    
  }

  NcFile::~NcFile()
  {
    close();
  }
  
  
  
  NcGroup*  NcFile::addGroup(string name)
  {
    return myRootGroup->addGroup(name);
  }
    
  NcGroup*  NcFile::addGroup(string name,int id)
  {
    return myRootGroup->addGroup(name,id);
  }
  
  NcFile::FillMode NcFile::getFill( void ) const       // get fill-mode
  {
    return myFillMode;
  }
  
  NcFile::FileFormat NcFile::getFormat( void ) const   // get format version
  {
    int temp;
    nc_inq_format(myId,&temp);
    return (FileFormat)temp;
  }
  
  bool NcFile::sync( void )                   // synchronize to disk
  {
    return nc_sync(myId);
  }
  
  bool NcFile::close( void )                  // to close earlier than dtr
  {
    if(isOpen)
      {
	isOpen = false;
	return nc_close(myId);
      }
    return false;
  }

  bool NcFile::abort( void )                  // back out of bad defines
  {
    return nc_abort(myId);
  }
   
  // Needed by other Nc classes, but users will not need them
  bool NcFile::defineMode( void ) // leaves in define mode, if possible
  {
    int ret; 
    if((ret = nc_redef(myId)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    
    inDefineMode = true;
    return true;
  }
  
  
  bool NcFile::dataMode( void )   // leaves in data mode, if possible
  {
    if( nc_enddef(myId)!=NC_NOERR)
      {
	throw NcException("Unable to enter data mode",__FILE__,__LINE__,__FUNCTION__);
      }
    else
      inDefineMode = false;
    return true;
  }
  
  int NcFile::getId( void ) const       // id used by C interface
  {
    return myId;
  }


  string NcFile::getName() const
  {
    return myName;
  }

  bool NcFile::isReadOnlyMode()
  {
    return inReadOnlyMode;
  }
  
  ////////////////////////
  //modifiers
  NcDim* NcFile::addDim( string dimName, long size )  //adds a dimension to the root group
  {
    // NcDim* temp= new NcDim(this,dimName,size);
    return myRootGroup->addDim(dimName, size);
  }
   
  NcDim* NcFile::addDim(string dimName)
  {
    return myRootGroup->addDim(dimName);
  }
   
  NcVar* NcFile::addVar( string varName, NcType type, const NcDim* dim0, 
			 const NcDim* dim1, 
			 const NcDim* dim2,
			 const NcDim* dim3,
			 const NcDim* dim4)  //adds a variable with 0-5 dimensions 
  {
    
    return  myRootGroup->addVar(varName,type,dim0,dim1,dim2,dim3,dim4);  
    //adds a variable to the root group
  }
   
  //adds a variable with more than five dimensions
  NcVar* NcFile::addVar( string varName, NcType type, int numDims, const NcDim** dim1 )
  {
    return myRootGroup->addVar(varName,type,numDims,dim1);
  }
  NcVar* NcFile::addVar( string varName, NcUserDefinedType* type)  //adds a variable with 0-5 dimensions 
  {
    return  myRootGroup->addVar(varName,type);
  
  } 

  NcCompoundType* NcFile::addCompoundType( string typeName,int shape)  //adds a variable with 0-5 dimensions
  {
    
    NcCompoundType* temp=NULL;
    try
      {
	temp = new NcCompoundType(myRootGroup, shape, typeName);
      }
    catch(NcException e)
      {
	e.what();
      }
   
    myCompoundTypes.insert(pair<string,NcCompoundType*>(typeName,temp));
    return temp;
  }
 
  NcEnumType* NcFile::addEnumType( string typeName)  //adds a variable with 0-5 dimensions
  {
    map<string,NcEnumType *>::iterator p;  
    NcEnumType * temp;
    p= myEnumTypes.find(typeName);
    if((p == myEnumTypes.end()))  // type hasn't already been added to file                                                
      {
	temp = new NcEnumType(myRootGroup,typeName);  //currently on only integers are support
	myEnumTypes.insert(pair<string,NcEnumType*>(typeName,temp));
      }
      
    return temp;
     
  }
   
  NcVLenType* NcFile::addVLenType( string typeName, NcType type)  

  {
    NcVLenType * temp;
    map<string,NcVLenType *>::iterator p;  
    p= myVLenTypes.find(typeName);
    if((p == myVLenTypes.end()))  // type hasn't already been added to file                                                
      {
	temp = new NcVLenType(myRootGroup,typeName,type);
	myVLenTypes.insert(pair<string,NcVLenType*>(typeName,temp)); 
      }
    return temp;
  }

  NcOpaqueType* NcFile::addOpaqueType(string typeName, int size)
  {
    NcOpaqueType * temp;
    map<string,NcOpaqueType*>::iterator p;
    p = myOpaqueTypes.find(typeName);
     
    if(p == myOpaqueTypes.end())
      {
	temp = new NcOpaqueType(myRootGroup,typeName,size);
	myOpaqueTypes.insert(pair<string,NcOpaqueType*>(typeName,temp));
      }
    return temp;
      
  }
   
  
  NcGroup * NcFile::getRootGroup()
  {
    return myRootGroup;
  }
  
  NcGroup * NcFile::getGroup(string name)const
  {

    return myRootGroup->getGroup(name);
  }
    
  NcDim* NcFile::getDim( string name ) 
  {
    return myRootGroup->getDim(name);
  }
   
  NcVar* NcFile:: getVar( string name) 
  {
    //cout<<"file's getVar method was was called"<<endl;
    return myRootGroup->getVar(name);
  }

  NcAtt* NcFile::getAtt( string name ) 
  {
    return  myRootGroup->getAtt(name);
  }
   
  NcGroup* NcFile::getGroup(string name)
  {
    return myRootGroup->getGroup(name);
  }
   
  NcDim* NcFile::getDim( int i ) 
  {
    return myRootGroup->getDim(i);
  }
      
  NcVar* NcFile::getVar( int i ) 
  {
    return myRootGroup->getVar(i);
  }
   
  NcAtt* NcFile:: getAtt( int i)
  {
    return myRootGroup->getAtt(i);
  }

  NcDim* NcFile::getUnlimDim( void)
  {
    return myRootGroup->getUnlimDim();
  }

  int NcFile::getNumDims()
  {
    //cout<<"about to call group getNumDims"<<endl;
    return myRootGroup->getNumDims();
  }
  int NcFile:: getNumAtts()               //get number of attributes
  {
    return myRootGroup->getNumAtts();
  }
  int NcFile::getNumVars()               //get number of variables
  {
    return myRootGroup->getNumVars();
  }
}

