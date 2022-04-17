/* 
   This is part of the netCDF-4 package. Copyright 2005 University
   Corporation for Atmospheric Research/Unidata See COPYRIGHT file for
   conditions of use. See www.unidata.ucar.edu for more info.

   This file contains the implementation of the NcValues class
   
   $Id: ncvalues.cpp,v 1.7 2007/07/31 15:37:56 forbes Exp $
*/

#include <config.h>
#include <netcdfcpp4.h>
#include <sstream>

namespace netCDF
{
  using namespace std;

  NcValues::NcValues(NcVar * var)
  {
    myVariable = var;
    int c = var->getNumDims();
    int k = 1;
    for(int i= 0; i < c; i++)
      {
	k*= var->getDim(i)->getSize();
      }//determines how much space needs to be allocated for the data, I dont know if this will work for vlen data

    myData = new float[k];
    nc_get_var(myVariable->getNcId(),myVariable->getId(), myData);
  }

  NcValues::~NcValues()
  {
    delete  myData;
  }
         
  //overloaded operators
  NcValues& NcValues::operator=(NcValues & rhs)  //not sure if this is necessary at all
  { //do a deep copy

    myVariable =rhs.myVariable;
    int c = myVariable->getNumDims();
    int k = 1;
    for(int i= 0; i < c; i++)
      {
	k*= myVariable->getDim(i)->getSize();
      }//determines how much space needs to be allocated for the data, I dont know if this will work for vlen data

    myData = new float[k];
    for(int i = 0;i< k;i++ )
      {
	myData[i]= rhs.myData[i];
      }

    //return this;

  }

  bool NcValues::operator==(NcValues & rhs)
  {//is this enough to check or do i need to check other things
    return myVariable == rhs.myVariable;
  }
  
  //accessors
  size_t NcValues::getNum()
  {
    return getSize();
  }
   

  size_t NcValues::getSize()
  {
      
    int c = myVariable->getNumDims();
    int k = 1;
    for(int i= 0; i < c; i++)
      {
	k*= myVariable->getDim(i)->getSize();
      }
    return k;

  }
  float* NcValues:: getData()
  {
    return 0;   // not sure what this is supposed to return, what if you don't know what kind of data you're dealing with
  }

  ostream& NcValues::print(ostream& os)const  //works for up to 2D, not sure how to handle higher dimensions output wise
  {
    int s = 1;
    s = myVariable->getNumDims();
    int ndims[s];
    for(int k = 0; k < s; k++)
      ndims[k] = myVariable->getDim(k)->getSize();

    if(s >1)
      {
	for(int i = 0; i < ndims[0]; i++ )
	  {
	    for(int j = 0; j < ndims[1]; j++)  // need to fix this
	      os<<myData[(i*ndims[0])+j]<<" ";
	    os<<endl;
	  }
      }
    else
      {
	for(int i = 0; i < ndims[0]; i++ )
	  os<<myData[i]<<" ";
	os<<endl;
      }
    
    return os;
  }
  
  ncbyte NcValues::toNcByte(size_t n)
  {
    return 0;
  }
  char NcValues::toChar(size_t n) // if it contains 30 it returns 3, need to fix this
  {
    stringstream  myStream;  
    myStream << myData[n];
    char k;
    myStream>> k;
    return k;
  }
   
  short NcValues::toShort(size_t n)
  {
    stringstream  myStream;  
    myStream << myData[n];
    short k;
    myStream>> k;
    return k;
  }

  int NcValues::toInt(size_t n)
  {
    stringstream  myStream;  
    myStream << myData[n];
    int k;
    myStream>> k;
    return k;
  }

  nclong NcValues::toNcLong(size_t n)
  {
    return 0;
  }
  long NcValues::toLong(size_t n)
  {
    stringstream  myStream;  
    myStream << myData[n];
    long k;
    myStream>> k;
    return k;
  }
  
  string NcValues::toString()
  {
    
    stringstream  myStream;
    // for all the data, add to the stream
    for (int i = 0; i < getSize(); i++)
      {
	myStream << myData[i]<<" ";
      }
      
    return myStream.str();
      
  }
 
}
