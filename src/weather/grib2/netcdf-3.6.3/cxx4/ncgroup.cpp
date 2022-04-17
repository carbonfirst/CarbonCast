/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the NcGroup class
   
   $Id: ncgroup.cpp,v 1.17 2007/07/31 15:37:56 forbes Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>

namespace netCDF
{
  using namespace std;

  NcGroup::NcGroup(int parentId,NcFile * parentFile)//private utility constructor   //used when the file is readonly 
  {
    myNcId=parentId;
    myId=parentId;
    theFile = parentFile;
    varCount = 0;
    attCount = 0;
    dimCount = 0;
  }
  
  NcGroup::NcGroup(NcGroup* parent, string name)
  {
    int ret;
    myName = name;
    myId = 0;
    varCount = 0;
    attCount = 0;
    dimCount = 0;
    theFile = parent->theFile;
    //check to see if in readOnlyMode, if not then define
    if(!isReadOnlyMode())
      {
	if ((ret = nc_def_grp(parent->getId(), (char *)name.c_str(), &myId)))
	  throw NcException(nc_strerror(ret) ,__FILE__,__LINE__, __FUNCTION__);
      } 

    myNcId = parent->getId();
    theFile = parent->theFile;
  }

  NcGroup::NcGroup(NcGroup* parent, string name,int id)
  {
    int ret;
    varCount = 0;
    attCount = 0;
    dimCount = 0;
    myName = name;
    myId = id;
    theFile = parent->theFile;
    myNcId = parent->getId();
    //check to see if in readOnlyMode, if not then define
    if(!isReadOnlyMode())
      {
	if ((ret = nc_def_grp(parent->getId(), (char *)name.c_str(), &myId)))
	  throw NcException(nc_strerror(ret) ,__FILE__,__LINE__, __FUNCTION__);
      }   
  }

  
  NcGroup::NcGroup(int parentId, std::string name, NcFile * thefile)//not sure if 0 for parent id is appropriate
  {
    int ret;
    myName = name;
    myId = 0;
    varCount = 0;
    attCount = 0;
    dimCount = 0;
    theFile = thefile;
    if(!isReadOnlyMode())
      if((ret =nc_def_grp(parentId, (char *)name.c_str(), &myId)))
	throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
  }
  
  NcGroup::NcGroup()
  {               
    myName="defaultname";
    myId = -5985565;
    varCount = 0;
    attCount = 0;
    dimCount = 0;
  }
  
  NcGroup::~NcGroup()
  {
    
    //not sure if the maps need to be deallocated here.
    //how do I remove a group??? do i need to?
    // H5Gclose(myId);
  }
   
  bool NcGroup::isReadOnlyMode()
  {
    return theFile->isReadOnlyMode();
  }
  
  NcDim *  NcGroup::addDim(std::string dimName, long dimSize)//adds a dimension to the group
  {
    NcDim * temp = new NcDim(this, dimName, (int)dimSize);
    if(temp==0)
      throw NcException("Error allocating dimension",__FILE__,__LINE__,__FUNCTION__);
    else
      {
	myDimensions.insert(pair<std::string,NcDim*>(dimName,temp));
	dimCount++;
	//cout<<"incremented dimcount"<<endl;
      }
    return temp;
  }
  NcDim *  NcGroup::addDim(std::string dimName, long dimSize,int id)//adds a dimension to the group
  {
    NcDim * temp = new NcDim(this, dimName, (int)dimSize,id);
    if(temp==0)
      throw NcException("Error allocating dimension",__FILE__,__LINE__,__FUNCTION__);
    else
      {
	myDimensions.insert(pair<std::string,NcDim*>(dimName,temp));
	dimCount++;
	//cout<<"incremented dimcount"<<endl;
      }
    return temp;
  }


  NcDim* NcGroup::addDim(std::string dimName)
  {
    NcDim* temp = new NcDim(this,dimName);
    if(temp==0)
      throw NcException("Error allocating dimension",__FILE__,__LINE__,__FUNCTION__);
    else
      {
	myDimensions.insert(pair<std::string,NcDim*>(dimName,temp));
	
	dimCount++;
	//cout<<"incremented dimcount"<<endl;
      }
    return temp;
      
  }
   

  NcVar* NcGroup::addVar( std::string varName, NcType type, const NcDim* dim0, 
			  const NcDim* dim1, 
			  const NcDim* dim2,
			  const NcDim* dim3,
			  const NcDim* dim4,int id)  //adds a variable with 0-5 dimensions
  {
    varCount++;   //increments the # of variables
    //cout<<"incremented varcount"<<endl;
    int dims[5];
    int ndims = 0;
    if (dim0)
      {
	ndims++;
	dims[0]=dim0->getId();	
	if (dim1) 
	  {
	    ndims++;
	    dims[1] = dim1->getId();
	    if (dim2) 
	      {
		ndims++;
		dims[2] = dim2->getId();
		if (dim3) 
		  {
		    ndims++;
		    dims[3] = dim3->getId();
		    if (dim4)
		      {
			ndims++;
			dims[4] = dim4->getId();
		      }
		  }//end if(dim3)
	      }//end if(dim2)
	  }//end if(dim1)
      }//end if(dim0)
    // int n = num_vars();
      
    NcVar* var = new NcVar(this,varName.c_str(), (nc_type) type, ndims,&dims[0],id);
    myVariables.insert(make_pair(varName,var));  //keeps track of the variables that have been added
    return var;
  }

  //adds a variable with more than five dimensions
  NcVar*  NcGroup::addVar( std::string varName, NcType type, int numDims, const NcDim** dim1,int id )
  {
    varCount++;   //increments the # of variables
    int dims[numDims];
    int ndims = 0;

    for( int i = 0;i < numDims; i++)
      {
	dims[i]=dim1[i]->getId();
      }
      
    NcVar* var = new NcVar(this,varName.c_str(), (nc_type) type, numDims,&dims[0],id);
    myVariables.insert(make_pair(varName,var));  //keeps track of the variables that have been added
    return var;
  }


  NcVar* NcGroup::addVar(string varName, NcUserDefinedType* type)
  {
    int ret =0;
    varCount++;   //increments the # of variables
    cout<<"add var has been called for a variable "<<varName<<endl;
    NcVar* var = new NcVar(this,varName.c_str(),type);
    myVariables.insert(make_pair(varName,var));  //keeps track of the variables that have been added
    cout<<"the variable has been successfully created"<<endl;
    return var;
  }


  NcGroup* NcGroup::addGroup(std::string name) // adds a sub group
  { 
    NcGroup *temp = new NcGroup(this, name); //call Group constructor here 
    myGroups.insert(make_pair(name, temp)); //keeps track of the added subgroups
    return temp;  //return a pointer to the newly created group
  }

  NcGroup* NcGroup::addGroup(std::string name, int id) // adds a sub group
  { 
    NcGroup *temp = new NcGroup(this, name,id); //call Group constructor here 
    myGroups.insert(make_pair(name, temp)); //keeps track of the added subgroups
    return temp;  //return a pointer to the newly created group
  }
  
  int NcGroup::getNumDims()    //returns the number of dimensions
  {
    //cout<<"about to return "<<dimCount<<" dimensions"<<endl;
    return dimCount;
  }
  
  int NcGroup:: getNumAtts()               //get number of attributes
  {
    //cout<<"about to return "<<attCount<<" attributes"<<endl;
    return attCount;
  }
  
  int NcGroup::getNumVars()               //get number of variables
  {
    //cout<<"about to return "<<varCount<<" variables"<<endl;
    return  varCount;
  }
  
  std::string NcGroup::getName() const           //get the name of the file
  {
    return myName;
  }

  NcGroup* NcGroup::getGroup(string grpn)
  {
    groupIterator = myGroups.find(grpn);
    if(groupIterator != myGroups.end()) // group was found
      return groupIterator->second;
    else
      return 0;
  }
  
  NcDim* NcGroup::getDim( string dimn )        // dimension by name
  {
    dimensionIterator = myDimensions.find(dimn);
    if(dimensionIterator != myDimensions.end())//dimension was found
      return dimensionIterator->second;   
    else
      return 0;

  }
  
  NcVar* NcGroup::getVar( string varn)        // variable by name
  {
  
    variableIterator = myVariables.find(varn);
    if(variableIterator != myVariables.end())    //variable was found
      return variableIterator->second;
    else 
      return 0;
  }
  
  NcAtt* NcGroup:: getAtt( std::string attn)        // global attribute by name
  {
    attributeIterator = myAttributes.find(attn);
    if(attributeIterator != myAttributes.end())
      return attributeIterator->second;
    else
      return 0;
  }
  
  NcDim* NcGroup::getDim( int n )            //pass in the dimension id  
  {
    string name;
    int i;

    for(dimensionIterator = myDimensions.begin(); dimensionIterator != myDimensions.end(); dimensionIterator++ )
      {
	i = dimensionIterator->second->getId();
	if( i == n)
	  break;
      }
    return dimensionIterator->second;
  }
  
  NcVar* NcGroup::getVar( int n )            // n-th variable
  {
    variableIterator = myVariables.begin();
    for(int i = 0; i<n; i++)
      variableIterator++;

    return variableIterator->second;
  }
  
  NcAtt* NcGroup::getAtt( int n )            // n-th global attribute
  {
    attributeIterator = myAttributes.begin(); 
    
    for(int i = 0; i < n; i++)
      attributeIterator++;
    
    return attributeIterator->second;
  }
  
  NcDim* NcGroup::getUnlimDim( void )           // unlimited dimension, if any  ???
  {  //should be able to do the same thing as 

    dimensionIterator = myDimensions.begin(); 

    while(dimensionIterator != myDimensions.end())  // not the last known dimension
      {
	if(dimensionIterator->second->isUnlimited()) // if unlimited
	  return dimensionIterator->second;          //return pointer to this dimensio
	else
	  dimensionIterator++;
      }
    return 0; // no unlimited dimensions
  }
  
  
  bool NcGroup::operator==(NcGroup & rhs)
  {
    if(&rhs!=NULL)
      {
	return myId == rhs.myId;  //hopefully this is all Ineed to check
	
      }
  }  

  NcGroup& NcGroup::operator=(NcGroup & rhs)
  {
    
    myId = rhs.myId;
    dimCount = rhs.dimCount;
    groupCount = rhs.groupCount;
    varCount = rhs.varCount;
    attCount = rhs.attCount;
    myName = rhs.myName;
    //hopefully the assignments below works
    myGroups = rhs.myGroups;
    myDimensions = rhs.myDimensions;
    myVariables = rhs.myVariables;
    myAttributes = rhs.myAttributes;
    return *this;
  }

  int NcGroup::getNcId() const
  {
    return myNcId;
  }
  
  int NcGroup::getId() const
  {
    return myId;
  }
  
  //groupIterator methods
  
  NcGroup::grpIterator NcGroup::beginGrp()
  {
    return NcGroup::grpIterator(this);
  }
  
  NcGroup::grpIterator NcGroup::endGrp()
  {//I don't think this implementation is correct
    
    return NcGroup::grpIterator(this,1);//calls the constructor that points to the end
  }
  
  NcGroup::grpIterator:: grpIterator(NcGroup *rhs)
  {
      
    groupIterator = rhs->myGroups.begin(); 
  }
  
  NcGroup::grpIterator::grpIterator(NcGroup::grpIterator * rhs )
  {
    groupIterator = rhs->groupIterator;
  }

  NcGroup::grpIterator::grpIterator()
  {
    //do nothing, assume this = something will be called later 
  }
  NcGroup::grpIterator::grpIterator(NcGroup *rhs,int i)//default iterator constructor
  {
    groupIterator = rhs->myGroups.end();    
  }

  NcGroup::grpIterator::~grpIterator()
  {
    //do nothing
  }
  
  NcGroup::grpIterator& NcGroup::grpIterator::operator=(const NcGroup::grpIterator & rhs)
  {
    groupIterator = rhs.groupIterator;
  }
  
  bool NcGroup::grpIterator::operator!=(const NcGroup::grpIterator & rhs)
  {
    return !( groupIterator == rhs.groupIterator);
  }
  
  NcGroup & NcGroup::grpIterator::operator*()
  {
    return *groupIterator->second;
  }
  
  NcGroup* NcGroup::grpIterator::operator->()
  {
    return groupIterator->second;
  }
  
  NcGroup::grpIterator& NcGroup::grpIterator::operator++()
  {
    groupIterator++;
    return *this;
  }
  
  NcGroup::grpIterator& NcGroup::grpIterator::operator++(int)
  {
    groupIterator++;
    if(groupIterator->second == NULL)
      {

      }
    return *this;
  }
  
  bool NcGroup::grpIterator::operator==(const NcGroup::grpIterator& rhs)
  {
    return groupIterator == rhs.groupIterator;;
  }
  
  //variableIterator methods
  NcGroup::varIterator NcGroup::beginVar()
  {
    return NcGroup::varIterator(this);
  }
  
  NcGroup::varIterator NcGroup::endVar()
  {//I don't think this implementation is correct
    
    return NcGroup::varIterator(this,1);//calls the constructor that points to the end
  }
  
  NcGroup::varIterator:: varIterator(NcGroup *rhs)
  {
    variableIterator = rhs->myVariables.begin();  
  }
  
  NcGroup::varIterator::varIterator(NcGroup::varIterator * rhs )
  {
    variableIterator = rhs->variableIterator;
  }

  NcGroup::varIterator::varIterator()
  {
    //do nothing, assume operator=() will be called later 
  }
  
  NcGroup::varIterator::varIterator(NcGroup *rhs,int i)//default iterator constructor
  {
    variableIterator = rhs->myVariables.end();        
  }

  NcGroup::varIterator::~varIterator()
  {
    //do nothing
  }
  
  NcGroup::varIterator& NcGroup::varIterator::operator=(const NcGroup::varIterator & rhs)
  {
    variableIterator = rhs.variableIterator;
  }
  
  bool NcGroup::varIterator::operator!=(const NcGroup::varIterator & rhs)
  {
    return !( variableIterator == rhs.variableIterator);
  }
  
  NcVar & NcGroup::varIterator::operator*()
  {
    return *variableIterator->second;
  }
  
  NcVar* NcGroup::varIterator::operator->()
  {
    return variableIterator->second;
  }
  
  NcGroup::varIterator& NcGroup::varIterator::operator++()
  {
    variableIterator++;
    return *this;
  }
  
  NcGroup::varIterator& NcGroup::varIterator::operator++(int)
  {
    variableIterator++;
    return *this;
  }
  
  bool NcGroup::varIterator::operator==(const NcGroup::varIterator& rhs)
  {
    return variableIterator == rhs.variableIterator;;
  }

  //dimension iterator methods 
  NcGroup::dimIterator NcGroup::beginDim()
  {
    return NcGroup::dimIterator(this);
  }
  
  NcGroup::dimIterator NcGroup::endDim()
  {//I don't think this implementation is correct
    
    return NcGroup::dimIterator(this,1);//calls the constructor that points to the end
  }
  
  NcGroup::dimIterator::dimIterator(NcGroup *rhs)
  {
    dimensionIterator = rhs->myDimensions.begin();  
  }
  
  NcGroup::dimIterator::dimIterator(NcGroup::dimIterator * rhs )
  {
    dimensionIterator = rhs->dimensionIterator;
  }

  NcGroup::dimIterator::dimIterator()
  {
    //do nothing, assume operator=() will be called later 
  }
  
  NcGroup::dimIterator::dimIterator(NcGroup *rhs,int i)//default iterator constructor
  {
    dimensionIterator = rhs->myDimensions.end();        
  }

  NcGroup::dimIterator::~dimIterator()
  {
    //do nothing
  }
  
  NcGroup::dimIterator& NcGroup::dimIterator::operator=(const NcGroup::dimIterator & rhs)
  {
    dimensionIterator = rhs.dimensionIterator;
  }
  
  bool NcGroup::dimIterator::operator!=(const NcGroup::dimIterator & rhs)
  {
    return !( dimensionIterator == rhs.dimensionIterator);
  }
  
  NcDim & NcGroup::dimIterator::operator*()
  {
    return *dimensionIterator->second;
  }
  
  NcDim* NcGroup::dimIterator::operator->()
  {
    return dimensionIterator->second;
  }
  
  NcGroup::dimIterator& NcGroup::dimIterator::operator++()
  {
    dimensionIterator++;
    return *this;
  }
  
  NcGroup::dimIterator& NcGroup::dimIterator::operator++(int)
  {
    dimensionIterator++;
    return *this;
  }
  
  bool NcGroup::dimIterator::operator==(const NcGroup::dimIterator& rhs)
  {
    return dimensionIterator == rhs.dimensionIterator;;
  }
  
  
  //attribute iterator methods
  NcGroup::attIterator NcGroup::beginAtt()
  {
    return NcGroup::attIterator(this);
  }
  
  NcGroup::attIterator NcGroup::endAtt()
  {
    
    return NcGroup::attIterator(this,1);//calls the constructor that points to the end
  }
  
  NcGroup::attIterator::attIterator(NcGroup *rhs)
  {
    attributeIterator = rhs->myAttributes.begin();  
  }
  
  NcGroup::attIterator::attIterator(NcGroup::attIterator * rhs )
  {
    attributeIterator = rhs->attributeIterator;
  }

  NcGroup::attIterator::attIterator()
  {
    //do nothing, assume operator=() will be called later 
  }
  
  NcGroup::attIterator::attIterator(NcGroup *rhs,int i)//default iterator constructor
  {
    attributeIterator = rhs->myAttributes.end();        
  }

  NcGroup::attIterator::~attIterator()
  {
    //do nothing
  }
  
  NcGroup::attIterator& NcGroup::attIterator::operator=(const NcGroup::attIterator & rhs)
  {
    attributeIterator = rhs.attributeIterator;
  }
  
  bool NcGroup::attIterator::operator!=(const NcGroup::attIterator & rhs)
  {
    return !( attributeIterator == rhs.attributeIterator);
  }
  
  NcAtt & NcGroup::attIterator::operator*()
  {
    return *attributeIterator->second;
  }
  
  NcAtt* NcGroup::attIterator::operator->()
  {
    return attributeIterator->second;
  }
  
  NcGroup::attIterator& NcGroup::attIterator::operator++()
  {
    attributeIterator++;
    return *this;
  }
  
  NcGroup::attIterator& NcGroup::attIterator::operator++(int)
  {
    attributeIterator++;
    return *this;
  }
  
  bool NcGroup::attIterator::operator==(const NcGroup::attIterator& rhs)
  {
    return attributeIterator == rhs.attributeIterator;
  }
 
}
