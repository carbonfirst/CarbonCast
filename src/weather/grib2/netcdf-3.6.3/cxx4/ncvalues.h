/*

Below is an attempt to combine the NcValues class in the netCDF-3 C++
interface with the array.h class presented in the wrapper library by
Fei Liu. Multidimensional NcValues creation is facilitated through
overloaded constructors and

//should I provide an iterator for the NcValues class???

*/

#include <exception>
#include <string>
#include <iostream>
#include <netcdf.h>
//#include "nciterator.h"

namespace netCDF 
{
#ifndef _netcdfstuff__
#define _netcdfstuff__
#define NC_UNSPECIFIED ((nc_type)0)
  
  typedef std::string NcToken;
  typedef bool NcBool;
  typedef std::string NcGroupName;
  typedef unsigned char ncbyte;
  
  
  //This shouldn't be here but lets see if it gets rid of some of my errors. I'm doing something wrong in
//the include files if this works
  /* The folloing are use internally in support of user-defines types. */
#define	NC_VLEN 	13	/* used internally for vlen types */
#define	NC_OPAQUE 	14	/* used internally for opaque types */
#define	NC_ENUM 	15	/* used internally for enum types */
#define	NC_COMPOUND 	16	/* used internally for compound types */
  
  
  
  enum NcType 
    {
      ncNoType   = NC_UNSPECIFIED, 
      ncByte     = NC_BYTE, 
      ncChar     = NC_CHAR, 
      ncShort    = NC_SHORT, 
      ncInt      = NC_INT,
      ncLong     = NC_LONG,  // deprecated, someday want to use for 64-bit ints
      ncFloat    = NC_FLOAT, 
      ncDouble   = NC_DOUBLE,
      ncVarLen   = NC_VLEN,
      ncOpaque   = NC_OPAQUE,
      ncEnum     = NC_ENUM,
      ncCompound = NC_COMPOUND
    };
#endif

  template <class T> class NcValues 
    {
    public:
      //constructors
      NcValues(void);
      
  /*copy constuctor,*/
      NcValues(NcValues <T> & rhs); 
      //overloaded constructors for up to five dimensions
      
      NcValues(size_t s0);
      NcValues(size_t s0,size_t s1);
      NcValues(size_t s0,size_t s1,size_t s2);
      NcValues(size_t s0,size_t s1,size_t s2,size_t s3);
      NcValues(size_t s0,size_t s1,size_t s2,size_t s3,size_t s4);
      NcValues(size_t s0,size_t s1,size_t s2,size_t s3,size_t s4,size_t s5);
      
      //destructor
      ~NcValues();
      //accessors
      size_t num();  
      T* getData();
      size_t size();
      //virtual ncByte 
      //overloaded operators
      NcValues<T>& operator=(NcValues <T>& rhs);
      NcBool operator==(NcValues <T>& rhs);
      //this covers stuff for those who prefer access via fortran methods..
  //should I also include theoperator[]()  for those who prefer the c/c++ style of direct access
      T& operator()(size_t i0);  //allows direct access to a one dimensional portion of an array
      T& operator()(size_t i0,size_t i1);
      T& operator()(size_t i0,size_t i1,size_t i2);
      T& operator()(size_t i0,size_t i1,size_t i2,size_t i3);
      T& operator()(size_t i0,size_t i1,size_t i2,size_t i3,size_t i4);		// similar to accessing an index of an array by saying array[i0][i1][i2][i3][i4]
      
      /*  I think the syntax below is correct
	  T& operator[](size_t i0);  //allows direct access to a one dimensional portion of an array
  T& operator[](size_t i0,i1);
  T& operator[](size_t i0,size_t i1,size_t i2);
  T& operator[](size_t i0,size_t i1,size_t i2,size_t i3);
  T& operator[](size_t i0,size_t i1,size_t i2,size_t i3,size_t i4);		// similar to accessing an index of an array by saying array[i0][i1][i2][i3][i4]
  //T& operator[]
  */
      std::ostream& print(std::ostream&)const;
      ncbyte asNcByte(size_t n);
      char asChar(size_t n);
      short asShort(size_t n);
      int asInt(size_t n);
      nclong asNcLong();
      long asLong();
      std::string asString();
      //void print(std::ostream& outStrm);
    
      //void print(std::ostream& outStrm);template <class T> class NcIterator 
    public:  
      class NcIterator 
      {
      public:
	NcIterator(T & rhs );
	NcIterator();  //default constructor
	~NcIterator();
	NcIterator& operator=(const NcIterator &rhs);
	bool operator==(const NcIterator &rhs);
	bool operator!=(const NcIterator &rhs);
	T & operator*();
	T* operator->();
	NcIterator& operator++();
	NcIterator& operator=(const NcIterator& rhs);
	
	NcIterator& operator++(int);
	NcBool operator!=(const NcIterator& rhs);
	NcBool operator==(const NcIterator& rhs);
	
	NcIterator begin();
	NcIterator end;
	
      private:
	T* myData; //iterators data
	
    };
    


}

