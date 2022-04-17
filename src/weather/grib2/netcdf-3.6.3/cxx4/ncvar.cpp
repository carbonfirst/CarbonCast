/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the NcVar class
   
   $Id: ncvar.cpp,v 1.19 2007/07/31 15:37:56 forbes Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

#ifndef ncvarimp
#define ncvarimp

namespace netCDF
{
  using namespace std;

  NcVar::~NcVar( void )
  {
    delete[] the_cur;
    delete[] cur_rec;
    //delete[] the_name;
  }
  
  bool NcVar::isReadOnlyMode()
  {
    return myGroup->isReadOnlyMode();
  }
  
  string NcVar::getName( void ) const
  {
    return myName;

  }
  NcType NcVar::getType( void ) const
  {

    return (NcType)myType;
  }

  bool NcVar::isValid( void ) const
  {
    return valid;
  }

  int NcVar::getNumDims( void ) const         // dimensionality of variable
  {
    int ndims;
    nc_inq_varndims(myNcId, myId, &ndims);  //doing this may return an incorrect 
    //value if the file has been modified  
    return ndims;

  }
  NcDim* NcVar::getDim(string name)const
  {//should now return the value stored in the map used to iterate
    return myGroup->getDim(name);
  }

  NcDim* NcVar::getDim( int i ) const        // n-th dimension
  {//should return the ith dimension stored in map
    int ndim;
    int dims[NC_MAX_VAR_DIMS];
    int ret;

    if ((ret = nc_inq_varndims (myNcId, myId, &ndim)))
      throw NcException(nc_strerror(ret));
    if ((ret = nc_inq_vardimid (myNcId, myId, dims)))
      throw NcException(nc_strerror(ret));
     
    if(i<0 || i >= ndim)
      throw NcException("dimension out of bounds");

    return myGroup->getDim(dims[i]);//the group class returns dimesions by id number
  }    


  size_t * NcVar::edges( void ) const          // dimension sizes
  {
    size_t* evec = new size_t[getNumDims()];
    for(int i=0; i < getNumDims(); i++)
      evec[i] = getDim(i)->getSize();
    return evec;
  }
  
  int NcVar::getNumAtts( void ) const         // number of attributes
  {//should return numatts in the ncvar class
    return attCount;
  }
  
  NcAtt* NcVar::getAtt(std::string attn)     // attribute by name
  {
    attributeIterator = myAttributes.find(attn);
    if(attributeIterator != myAttributes.end())
      return attributeIterator->second;
    else
      return 0;
  }

  NcAtt* NcVar::getAtt( int n)         // n-th attribute
  {
    attributeIterator = myAttributes.begin();
    for(int i= 0; i < n; i++)
      attributeIterator++;
    return attributeIterator->second;
  }

  string NcVar::getAttName(int n)
  {
    attributeIterator = myAttributes.begin();
    for(int i= 0; i < n; i++)
      attributeIterator++;
    return attributeIterator->first;
  }
  
  
  
  /*really think about what these should do, see project to do list*/
  bool NcVar::setCur(size_t c0, size_t c1, size_t c2,
		     size_t c3, size_t c4)
  {
    
    long t[6];
    t[0] = c0;
    t[1] = c1;
    t[2] = c2;
    t[3] = c3;
    t[4] = c4;
    t[5] = -1;
    //I'm not sure what this block of code really does 
    for(int j = 0; j < 6; j++)
      { // find how many parameters were used
	int i;
	if (t[j] == -1)
	  {
	    if (getNumDims() < j)
	      return false;	// too many for variable's dimensionality
	    for (i = 0; i < j; i++)
	      {
		if (t[i] >= getDim(i)->getSize() && ! getDim(i)->isUnlimited())
		  return false;	// too big for dimension
		the_cur[i] = t[i];
	      }
	    for(i = j; i <getNumDims(); i++)
	      the_cur[i] = 0;
	    return true;
	  }
      }
    return true;
    
  }
  
  bool NcVar::setCur(size_t* cur)
  {
    the_cur = new size_t[sizeof(cur)];   // this may be incorrect
    cur_rec = new size_t[sizeof(cur)];   //this may be incorrect
    for(int i = 0; i <getNumDims(); i++)
      {
	if (cur[i] >= getDim(i)->getSize() && ! getDim(i)->isUnlimited())
	  return false;
	the_cur[i] = cur[i];
      }
    return true;
  }
  
  
  
  bool NcVar::rename( string newname )
  {
    int ret;
    if(ret = nc_rename_var(myNcId,myId,newname.c_str()))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    //throe exception if necessary
    return true;
  
  }
       
  size_t NcVar::recSize ( void )             // number of values per record
  {
    return recSize(getDim(0));
  }
  
  size_t NcVar::recSize ( NcDim* d )           // number of values per dimension slice
  {
    int idx = dimToIndex(d); 
    long size = 1;
    size_t* edge = edges();
    for( int i = 0 ; i<getNumDims() ; i++) 
      {
	if (i != idx) 
	  {
	    size *= edge[i];
	  }
      }
    delete [] edge;
    return size;
  }

  NcValues* NcVar::getRec(void)	        // get current record
  {
  
  }
  
  NcValues* NcVar::getRec(size_t rec)        // get specified record
  {
    return getRec(getDim(0), rec);
  }
 
  NcValues * NcVar::getRec(NcDim* d)        // get current dimension slice
  {

  }
  
  NcValues* NcVar::getRec(NcDim* d, size_t slice) // get specified dimension slice
  {
  
    int idx = dimToIndex(d);
    long size = getNumDims();
    size_t* start = new size_t[size];
    for (int i=1; i < size ; i++) start[i] = 0;
    start[idx] = slice;
    bool result = setCur(start);
    if (! result ) 
      {
	delete [] start;
	return 0;
      }
    
    size_t* edge = edges();
    edge[idx] = 1;
    // NcValues<W>* valp = getSpace(recSize(d));
    // if (ncvarget(myNcId, myId, start, edge, valp->base()) == ncBad) 
    //{
    //delete [] start;
    //delete [] edge;
    //delete valp;
    //return 0;
    //}
    //delete [] start;
    //delete [] edge;
    //return valp;
    return 0;
  }
  int NcVar::dimToIndex(NcDim *d)
  {
    string t1;
    string t2;
    for (int i=0; i < getNumDims() ; i++) 
      {

	t1 = getDim(i)->getName();
	t2 = d->getName();
	if (t2==t2) 
	  {
	    return i;
	  }
      }
    // we should fail and gripe about it here....
    return -1;
  }
 
  
  // Set current record
  void NcVar::setRec ( size_t rec )
  {
    // Since we can't ask for the record dimension here
    // just assume [0] is it.....
    setRec(getDim(0),rec);
    return;
  }

  // Set current dimension slice
  void NcVar::setRec ( NcDim* d, size_t slice )
  {
    int i = dimToIndex(d);
    // we should fail and gripe about it here....
    if (slice >= getDim(i)->getSize() && ! getDim(i)->isUnlimited())
      return;  
    cur_rec[i] = slice;
    return;
  }
       
  int NcVar::getId( void ) const           
  {
    return myId;
  }
  
  int NcVar::getNcId(void)
  {
    return myGroup->getNcId();
  }
  
 

  NcVar::NcVar( void )
  {
    attCount = 0;
    initCur();
  }


  NcVar::NcVar (NcGroup * grp, string name,nc_type type,int ndims,int dimids[], int id)
  {
    initCur();
    valid = false;
    attCount = 0;
    int ret;
    myGroup = grp;
   
    if(!isReadOnlyMode())
      {
	if(ndims)
	  {
	    if(( ret = nc_def_var(grp->myNcId,name.c_str(),type,ndims,dimids,&myId)))  //I'm not sure the (const int )*dimids is correct
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  }
	else
	  {
	    if(( ret = nc_def_var(grp->myNcId,name.c_str(),type,0,0,&myId)))  //I'm not sure the (const int )*dimids is correct
	      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	  
	  }
      }

    valid = true;
    myNcId = grp->myNcId;;
    myType =(NcType) type;
    myName = name;   
    myGroup->varCount++;
    if(isReadOnlyMode())
      {
	myId = id;
      }

  }

  NcVar::NcVar(NcGroup* grp,string varName,NcUserDefinedType* type)
  {
    initCur();
    int ret = 0;
    attCount = 0;
    valid = false;
    myGroup = grp;
    if(!isReadOnlyMode())
      if (ret = nc_def_var(grp->getNcId(),varName.c_str(), type->getId(), 0, NULL, &myId))  
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);

    valid = true;
    myNcId = grp->myNcId;;
    myType = (NcType)type->getType();
    myName = varName;   
    myGroup->varCount++;
  }
  
  
  //put for the compound type//maybe it will work for all user defined types
  bool NcVar::put(void * data)
  {
    cout<<"put has just been called for variable ";
    int ret;
    if(ret = nc_put_var(myGroup->getNcId(), myId,data))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__); 
    cout<<myName<<endl;
  }

  NcValues* NcVar::getValues( void ) 
  //not sure if this implementation is correct
  {
    
    NcValues *myval = new NcValues(this);
    return myval;
  }
  

  
  //attribute iterator methods
  NcVar::attIterator NcVar::beginAtt()
  {
    return NcVar::attIterator(this);
  }
  
  NcVar::attIterator NcVar::endAtt()
  {
    return NcVar::attIterator(this,1);//calls the constructor that points to the end
  }
  
  NcVar::attIterator::attIterator(NcVar *rhs)
  {
    attributeIterator = rhs->myAttributes.begin();  
  }
  
  NcVar::attIterator::attIterator(NcVar::attIterator * rhs )
  {
    attributeIterator = rhs->attributeIterator;
  }

  NcVar::attIterator::attIterator()
  {
    //do nothing, assume operator=() will be called later 
  }
  
  NcVar::attIterator::attIterator(NcVar *rhs,int i)//default iterator constructor
  {
    attributeIterator = rhs->myAttributes.end();        
  }

  NcVar::attIterator::~attIterator()
  {
    //do nothing
  }
  
  NcVar::attIterator& NcVar::attIterator::operator=(const NcVar::attIterator & rhs)
  {
    attributeIterator = rhs.attributeIterator;
  }
  
  bool NcVar::attIterator::operator!=(const NcVar::attIterator & rhs)
  {
    return !( attributeIterator == rhs.attributeIterator);
  }
  
  NcAtt & NcVar::attIterator::operator*()
  {
    return *attributeIterator->second;
  }
  
  NcAtt* NcVar::attIterator::operator->()
  {
    return attributeIterator->second;
  }
  
  NcVar::attIterator& NcVar::attIterator::operator++()
  {
    attributeIterator++;
    return *this;
  }
  
  NcVar::attIterator& NcVar::attIterator::operator++(int)
  {
    attributeIterator++;
    return *this;
  }
  
  bool NcVar::attIterator::operator==(const NcVar::attIterator& rhs)
  {
    return attributeIterator == rhs.attributeIterator;
  }
 
  
  void NcVar::initCur( void )  //I'm not sure what this does
  {
    //ut<<"init cur has been called"<<endl;
    the_cur = new size_t[MAX_NC_DIMS]; // *** don't know num_dims() yet?
    cur_rec = new size_t[MAX_NC_DIMS]; // *** don't know num_dims() yet?
    for(int i = 0; i < MAX_NC_DIMS; i++) 
      { 
	the_cur[i] = 0; cur_rec[i] = 0; 
      }
  }

  NcUserDefinedType::NcUserDefinedType()
  {
    myName = "defaultUserDefinedTypeName";
    mySize =0;
  }

  NcUserDefinedType::NcUserDefinedType(string name, int size, NcType type)
  {

  }

  NcUserDefinedType:: ~NcUserDefinedType()
  {

  }
  
  nc_type NcUserDefinedType::getType()
  {
    return myType;
  }
  
 
  string NcUserDefinedType::getName()
  {
    return myName;
  }


  int NcUserDefinedType::getId()
  {
    return myTypeId;
  }
  
  size_t NcUserDefinedType::getSize()
  {
    return mySize;
  }

  void NcUserDefinedType:: addMember(string memName,NcType type) // virtual function
  {}
  
  void NcUserDefinedType:: addMember(string memName,NcUserDefinedType* type) //virtual function
  {
  }
  
  //virtual void commit(); //virtual function
  void NcUserDefinedType::addMember(const char * memName,NcType type)
  {

  }
  
  void NcUserDefinedType::addMember(const char *memName,NcUserDefinedType* type)
  {

  }


  NcCompoundType::NcCompoundType(NcGroup *grp, int size, string name,int id)
  {
    int ret;
    valid = false;
    myOffset = 0;
    myTypeId = id;
    if(!grp->isReadOnlyMode())
      if((ret = nc_def_compound(grp->getNcId(), size,( char *) name.c_str(), &myTypeId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
     
    valid = true;
    myGroup = grp;
    myName = name;
    myOffset = 0;
    mySize=size;
    myType= NC_COMPOUND;
  }

  NcCompoundType::~NcCompoundType()
  {
  
  }

  void NcCompoundType::addMember( string memName, nc_type type)
  {
    int ret;
    if((ret = nc_insert_compound(myGroup->getNcId(),myTypeId,(char *)memName.c_str(),myOffset,type)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    myOffset+=sizeof(type);
      
  }
 
  size_t NcCompoundType::getSize()
  {
    return mySize;
  }

  void NcCompoundType::addMember (string memName, NcUserDefinedType * type)
  {
    int ret;
    if((ret = nc_insert_compound(myGroup->getNcId(),myTypeId,(char *)memName.c_str(),myOffset,type->getId())))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    myOffset+=type->getSize(); 
  }

  void NcCompoundType::addMember(const char *memName, NcType type)
  {
    addMember(string(memName),type);
  }

  void NcCompoundType::addMemeber(const char *memName,NcUserDefinedType * type)
  {
    addMember(string(memName),type);
  }

  
  
  NcEnumType::NcEnumType(NcGroup * group, string name, int id)
  {
    int ret;
    myGroup = group;
    myName = name;
    myTypeId = id;
    if(!group->isReadOnlyMode())
      if((ret = nc_def_enum(group->getNcId(),NC_INT,name.c_str(),&myTypeId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    
    valid = true;
    myType =  NC_ENUM;
    mySize = sizeof(int);
    
  }
  
  NcEnumType::~NcEnumType()
  {
    
  }
  
  void NcEnumType::addMember( string memName, int value)
  {
    int ret;
    if((ret = nc_insert_enum(myGroup->getNcId(),myTypeId,memName.c_str(),&value)))
      throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__); 
    //mySize+=sizeof(int);
  }

  size_t NcEnumType::getSize()
  {
    return mySize;
  }
  
  
  NcOpaqueType::NcOpaqueType(NcGroup *group, string name, size_t size, int id)
  {
    int ret;
    myTypeId = id;  //just incase it's read only
    mySize = size;
     
    myGroup = group;
    myName = name;
    myTypeId = id;
    if(!group->isReadOnlyMode())
      if((ret = nc_def_opaque(group->getNcId(),size,(char *)name.c_str(),&myTypeId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    valid = true;
    myType =  NC_OPAQUE;
       
  }
  
  NcOpaqueType::~NcOpaqueType()
  {
    
  }

  size_t NcOpaqueType::getSize()
  {
    return mySize;
  }
 
   
  NcVLenType::NcVLenType(NcGroup *group, string name, NcType type,int id)
  {
    
    int ret;
    myGroup = group;
    myName = name;
    myTypeId = type;//id;   //not sure if this is correct
    if(!group->isReadOnlyMode())
      if((ret = nc_def_vlen(group->getNcId(),(char *)name.c_str(),type,&myTypeId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
    valid = true;
    myType =  NC_VLEN;
  }
  
  NcVLenType::~NcVLenType()
  {
  
    //nc_free_vlen(myTypeId);
  }
  
  
  size_t NcVLenType::getSize()
  {
    return mySize;
  }
}

       
  
#endif

