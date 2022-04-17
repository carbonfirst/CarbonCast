#include <exception>
#include <string>
#include <iostream>
#include <cstdarg>
#include <cctype>
#include <cassert>
#include <cstring>
#include <set>
#include <map>
#include <stdio.h>
#include "netcdf.h"
#include <stdlib.h>
#include <sstream>

#ifndef _NETCDF4_H
#define _NETCDF4_H
#define NC_UNSPECIFIED ((nc_type)0)
using namespace std;


namespace netCDF
{
   class NcDim;
   class NcVar;
   class NcGroup;
   class NcAtt;
   class NcFile;
   class NcException;
   class NcUserDefinedType;
   class NcCompoundType;
   class NcEnumType;
   class NcVLenType;
   class NcOpaqueType;
   class NcValues;
   
   typedef signed char ncbyte;
  
   enum NcType 
      {
	 ncNoType   = NC_UNSPECIFIED, 
	 ncByte     = NC_BYTE, 
	 ncChar     = NC_CHAR, 
	 ncShort    = NC_SHORT, 
	 ncInt      = NC_INT,
	 ncFloat    = NC_FLOAT, 
	 ncDouble   = NC_DOUBLE,
	 ncUByte    = NC_UBYTE,
	 ncUShort   = NC_USHORT,
	 ncUInt     = NC_UINT,
	 ncInt64    = NC_INT64,
	 ncUInt64   = NC_UINT64,
	 ncString   = NC_STRING,
	 ncVLen     = NC_VLEN,
	 ncOpaque   = NC_OPAQUE,
	 ncEnum     = NC_ENUM,
	 ncCompound = NC_COMPOUND
      };
  
   class NcFile
   {
   public:
    
      enum FileMode 
	 {
	    ReadOnly,	// file exists, open read-only
	    Write,		// file exists, open for writing
	    Replace,	// create new file, even if already exists
	    New		// create new file, fail if already exists
	 };
    
      enum FileFormat 
	 {
	    Classic,         // netCDF classic format (i.e. version 1 format)
	    Offset64Bits,    // netCDF 64-bit offset format
	    Netcdf4,		// netCDF-4 using HDF5 format
	    Netcdf4Classic,	// netCDF-4 using HDF5 format using only netCDF-3 calls
	    BadFormat
	 };
    
      enum FillMode 
	 {
	    Fill = NC_FILL,                    // prefill (default)
	    NoFill = NC_NOFILL,                // don't prefill
	    Bad
	 };
    
    
      //constructor
      NcFile(string path, FileMode fMode, 
	     size_t* chunkSizePtr, size_t initialSize,
	     FileFormat fFormat);
      NcFile(string path,FileMode fMode=ReadOnly);
    
    
      //destructor
      virtual ~NcFile(); //closes file and releases all resources
      //modifiers
      NcGroup* addGroup(string);  //adds a subgroup to the root group
      NcDim* addDim( string dimName, long size );  //adds a dimension to the root group
      // NcDim* addDim(string, long int, int);
      NcDim* addDim(string dimName);  //adds and unlimited dimensions
      NcVar* addVar( string varName, NcType type, const NcDim* dim0, 
		     const NcDim* dim1 = 0, 
		     const NcDim* dim2 = 0,
		     const NcDim* dim3 = 0,
		     const NcDim* dim4 = 0);  //adds a variable with 0-5 dimensions 
    
      //adds a variable with more than five dimensions
      NcVar* addVar( string varName, NcType type, int numDims, const NcDim** dim1 );
      NcVar* addVar( string varName, NcUserDefinedType* type);  //adds a variable with 0-5 dimensions 
    
      NcCompoundType* addCompoundType( string typeName,int shape);  //adds a variable with 0-5 dimensions
      NcEnumType* addEnumType( string typeName);  //adds a variable with 0-5 dimensions
      NcVLenType* addVLenType( string typeName,NcType type);  //adds a variable with 0-5 dimensions
      NcOpaqueType* addOpaqueType( string typeName,int size);
    
    
      //NcGroup* addGroup( string name );// adds a sub group
      template <class T> NcAtt* addAtt(string attName,NcType type ,T value);
    
      bool setFill( FillMode = Fill );    // set fill-mode
      FillMode getFill( void ) const;       // get fill-mode
      FileFormat getFormat( void ) const;   // get format version
      int getNumDims();               //get number of dimensions
      int getNumAtts();               //get number of attributes
      int getNumVars();               //get number of variables
    
      bool sync( void );                   // synchronize to disk
      bool close( void );                  // to close before the call to the destructor
      bool abort( void );                  // back out of bad defines
    
      // Needed by other Nc classes, but users will not need them
      bool defineMode( void ); // leaves in define mode, if possible
      bool dataMode( void );   // leaves in data mode, if possible
      int getId( void ) const;       // id used by C interface
      bool isReadOnlyMode();    //true if in define mode, false if read-only
    
    
      //accessors
      string getName() const;           //get the name of the file
      NcDim* getDim( string name ) ;       // dimension by name
      NcVar* getVar( string name ) ;       // variable by name
      NcAtt* getAtt( string name ) ;       // global attribute by name
      NcGroup* getGroup( string name );     //get a group by name 
      NcDim* getDim( int i ) ;           // n-th dimension
      NcVar* getVar( int i ) ;           // n-th variable
      NcAtt* getAtt( int i ) ;           // n-th global attribute
      NcDim* getUnlimDim( void ) ;          // unlimited dimension, if any  ???

    
      NcGroup* getGroup( string )const;      //get a group by name
      NcGroup* getRootGroup();                   //returns a pointer to the root group
   private:
      NcFile();  //disable the default constructor
      void readGroups(NcGroup *group, int id);                        //used to read from an existing file
      void readAttributes(NcGroup*, int attCount);            //used to read from an existing file
      void readAttributes(NcVar*, int attCount);            //used to read from an existing file
      void readDimensions(NcGroup* group, int dimCount);      //used to read from an existing file
      void readVariables(NcGroup* group,int varCount);        //used to read from an existing file
      NcGroup* addGroup(string name, int id);  //adds a subgroup to the root group
      NcGroup *myRootGroup;   //every netCDF-4 file has a root group
      string myName;
      int myId;   //file's ncid from c interface
      int myMode;
      bool isOpen;
      bool inDefineMode;  //should this be a boolean data type instead of an int
      bool inReadOnlyMode;  // will need to be set and reset in constructor
      FillMode myFillMode;
      map<string,NcEnumType *>myEnumTypes;
      map<string,NcCompoundType *>myCompoundTypes;
      map<string,NcOpaqueType *>myOpaqueTypes;
      map<string,NcVLenType* >myVLenTypes;
      //FileFormat myFormat;
   };
  
  
   class NcAtt 
   {
   public:          
      string getName( void ) const;
      string getValue(void);  //returns the value of the attribue ie if the name is units the value can be celcius
      NcType getType( void ) const;
      size_t numVals( void ) const; //??? // is this necessary and if so what does it do
      NcValues* getValues( void );   //  should this be implemented instead of getValue()
      bool rename( string newname );
      bool remove( void );
      bool isValid( void );    //should strings have a particluar structure????
      int getId()
      {
	 return myId; 
      }    
      
      bool isReadOnlyMode();   //true if in define mode, false if read-only
   private:
      
      NcVar* myVariable;       //how do u differentiate group attributes from variable attributes
      NcGroup *myGroup;
      string myName;
      string myValue;
      int myNcId;
      int myId;
      bool valid;
      // protected constructors because only NcVar and NcGroup create
      // attributes
      template <class G>  NcAtt(NcGroup*, string,NcType ,G);//group attribute
      template <class G>  NcAtt(NcVar*, string,NcType,G); // variable attribute
      template <class G>  NcAtt(NcGroup*,string, NcUserDefinedType *,G);
      template <class G>  NcAtt(NcVar*, string,NcUserDefinedType*,G);
      virtual ~NcAtt( void );
      // To make attributes, since constructor is private
      friend class NcGroup;
      friend class NcVar;
      //friend NcAtt* exgetAtt( string );  //what did this do in the netCDF-3 interface??
   };
  
  
   class NcGroup
   {	
   public:
      class grpIterator 
      {
      private:
	 grpIterator(NcGroup *rhs,int i); //construcor that points to end of list
      public:
	 grpIterator(NcGroup *rhs);
	 grpIterator(NcGroup::grpIterator * rhs );
	 grpIterator();
	 ~grpIterator();
	 grpIterator& operator=(const NcGroup::grpIterator & rhs);
	 bool operator!=(const NcGroup::grpIterator & rhs);
	 NcGroup & operator*();
	 NcGroup* operator->();
	 grpIterator& operator++();
	 grpIterator& operator++(int);
	 bool operator==(const NcGroup::grpIterator& rhs);
	 map<string,NcGroup *>::const_iterator groupIterator;     
	 friend class NcGroup;
      }; 
    
      class varIterator 
      {
      private:
	 varIterator(NcGroup *rhs,int i); //construcor that points to end of list
      public:
	 varIterator(NcGroup *rhs);
	 varIterator(NcGroup::varIterator * rhs );
	 varIterator();
	 ~varIterator();
	 varIterator& operator=(const NcGroup::varIterator & rhs);
	 bool operator!=(const NcGroup::varIterator & rhs);
	 NcVar & operator*();
	 NcVar* operator->();
	 varIterator& operator++();
	 varIterator& operator++(int);
	 bool operator==(const NcGroup::varIterator& rhs);
	 map<string,NcVar *>::const_iterator variableIterator;     
	 friend class NcGroup;
      };
    
      class dimIterator 
      {
      private:
	 dimIterator(NcGroup *rhs,int i); //construcor that points to end of list
      public:
	 dimIterator(const NcGroup * rhs);
	 dimIterator(NcGroup *rhs);
	 dimIterator(NcGroup::dimIterator * rhs );
	 dimIterator();
	 ~dimIterator();
	 dimIterator& operator=(const NcGroup::dimIterator & rhs);
	 bool operator!=(const NcGroup::dimIterator & rhs);
	 NcDim & operator*();
	 NcDim* operator->();
	 dimIterator& operator++();
	 dimIterator& operator++(int);
	 bool operator==(const NcGroup::dimIterator& rhs);
	 map<string,NcDim *>::iterator dimensionIterator;     //was ::const_iterator
	 friend class NcGroup;
      };  
    
      class attIterator 
      {
      private:
	 attIterator(NcGroup *rhs,int i); //construcor that points to end of list
      public:
	 attIterator(NcGroup *rhs);
	 attIterator(NcGroup::attIterator * rhs );
	 attIterator();
	 ~attIterator();
	 attIterator& operator=(const NcGroup::attIterator & rhs);
	 bool operator!=(const NcGroup::attIterator & rhs);
	 NcAtt & operator*();
	 NcAtt* operator->();
	 attIterator& operator++();
	 attIterator& operator++(int);
	 bool operator==(const NcGroup::attIterator& rhs);
	 map<string,NcAtt *>::const_iterator attributeIterator;     
	 friend class NcGroup;
      };  
    
    
      NcGroup::grpIterator beginGrp();
      NcGroup::attIterator beginAtt();
      NcGroup::dimIterator beginDim();
      NcGroup::varIterator beginVar();
    
      NcGroup::grpIterator endGrp();
      NcGroup::attIterator endAtt();
      NcGroup::dimIterator endDim();
      NcGroup::varIterator endVar();
    
    
      //modifiers
      NcDim* addDim( string dimName, long );  //adds a dimension to the group
      NcDim* addDim( string dimName);
      NcDim* addDim( string dimName,long,int);  //specifies teh id to be assigned to the group, consider making private
      NcVar* addVar( string varName, NcType type, const NcDim* dim0, 
		     const NcDim* dim1 = 0, 
		     const NcDim* dim2 = 0,
		     const NcDim* dim3 = 0,
		     const NcDim* dim4 = 0,int id = 0);  //adds a variable with 0-5 dimensions 
     
    
      //adds a variable with more than five dimensions
      NcVar* addVar( string varName, NcType type, int numDims, const NcDim** dim1,int id = 0);
      
   
      NcVar* addVar(string varName, NcUserDefinedType * type); //adds a userdefined type variable
      //      NcVar* addVar( string varName, NcUserDefinedType* type ,int id = 0);
    
      NcGroup* addGroup(string myName);// adds a sub group
      template <class T> NcAtt* addAtt(string attName,NcType type,T value);
      template <class T> NcAtt* addAtt(string attName,NcUserDefinedType *type,T value);
      //accessors 
      int getNumDims();               //get number of dimensions
      int getNumAtts();               //get number of attributes
      int getNumVars();               //get number of variables
      string getName()const;           //get the name of the file
      NcDim* getDim( string ) ;       // dimension by name
      NcVar* getVar( string ) ;       // variable by name
      NcAtt* getAtt( string ) ;       // global attribute by name
      NcGroup* getGroup(string);     //get a group by name 
      NcDim* getDim( int ) ;           // n-th dimension
      NcVar* getVar( int ) ;           // n-th variable
      NcAtt* getAtt( int ) ;           // n-th global attribute
      NcDim* getUnlimDim( void ) ;          // unlimited dimension, if any  ???
      int getNcId()const;
      int getId()const;
      NcGroup& operator =(NcGroup &);
      bool operator==(NcGroup&);     
      bool isReadOnlyMode();
    
   private:
      NcGroup();                             //disable default constructor
      NcGroup(int parentId,NcFile *file);                //used when a file is ReadOnly
      NcGroup(int parentId,string,NcFile * file);       //used when creating the root group
      NcGroup(NcGroup*,string name); // constructor
      NcGroup(NcGroup*,string name,int id); // constructor
      ~NcGroup();//destructor
      NcGroup * addGroup(string name, int id);
      //keeps track of the variables, attributes, dimensions, and groups that have been added to the file 
      //idea of tracking taken from Fei Liu
      //information is stored in id order
      map <string,NcGroup *>myGroups;      //stores all groups that have been added to this group
      map <string,NcDim *> myDimensions;  //stores all dimensions that have been added to this group
      map <string,NcVar *> myVariables;  //stores all variables that have been added to this group
      map <string,NcAtt*> myAttributes;
      map<string,NcGroup *>::const_iterator groupIterator;
      map<string,NcDim *>::const_iterator dimensionIterator;
      map<string,NcVar *>::const_iterator variableIterator;
      map<string,NcAtt *>::const_iterator attributeIterator;
    
      string myName;
      int myId;	
      int myNcId;
      int dimCount;
      int groupCount;
      int varCount;
      int attCount;
      NcFile *theFile;
    
      friend class NcFile;
      friend class NcVar;
    
      friend class NcGroup::grpIterator;
      friend class NcGroup::varIterator;
      friend class NcGroup::attIterator;
      friend class NcGroup::dimIterator;
   };
  
   class NcDim
   {
   public:
      bool isUnlimited( void ) const;  //true if this is an unlimited dimension
      bool rename( string newname );  //renames the dimension
      string getName()const;     //returns the dimension name
      size_t getSize( void ) const;  //returns the size of the dimension
      NcGroup * getGroup();
      int getId()const;
      bool isReadOnlyMode();  //true if in define mode, false if readonly
   private:
      int myId;                  //dimension id
      int myNcId;                //id associated with the file
      string myName;            //dimension's  name
      NcGroup *theGroup;         //pointer to the group which own's this dimension 
      NcDim();                   //disabled default constructor
      NcDim(NcGroup* grp,string,size_t j); //creates a diminsion of size j, if j =0 an unlimited dimension is created
      NcDim(NcGroup* grp,string);  //creates an unlimited dimension
      NcDim(NcGroup* grp,string,size_t j,int id);
      NcDim* getDim( string );       // dimension by name
      NcDim* getDim();  //hopefully this is appropriate 
      ~NcDim();
      friend class NcGroup;
   };
  
    
   class NcVar
   {
   public:
    
      class attIterator 
      {
      private:
	 attIterator(NcVar *rhs,int i); //construcor that points to end of list
      public:
	 attIterator(NcVar *rhs);
	 attIterator(NcVar::attIterator * rhs );
	 attIterator();
	 ~attIterator();
	 attIterator& operator=(const NcVar::attIterator & rhs);
	 bool operator!=(const NcVar::attIterator & rhs);
	 NcAtt & operator*();
	 NcAtt* operator->();
	 attIterator& operator++();
	 attIterator& operator++(int);
	 bool operator==(const NcVar::attIterator& rhs);
	 map<string,NcAtt *>::const_iterator attributeIterator;     
	 friend class NcVar;
      };  
    
      NcVar::attIterator beginAtt();
      NcVar::attIterator endAtt();
      virtual ~NcVar( void );
      string getName( void ) const;
      NcType getType( void ) const;
      bool isValid( void ) const;
      virtual int getNumDims( void ) const;         // dimensionality of variable
      NcDim* getDim( int ) const;        // n-th dimension
      NcDim* getDim(string)const;
      size_t * edges( void ) const;          // dimension sizes
      int getNumAtts( void ) const;         // number of attributes
      virtual NcAtt* getAtt( string );    // attribute by name
      virtual NcAtt* getAtt( int ) ;        // n-th attribute
      bool isReadOnlyMode();  //true if in define mode, false if read only
      //long num_vals( void ) const;        // product of dimension sizes
      NcValues* getValues( void );     // returns a pointer to all the values
    
      // Put scalar or 1, ..., 5 dimensional arrays by providing enough
      // arguments.  Arguments are edge lengths, and their number must not
      // exceed variable's dimensionality.  Start corner is [0,0,..., 0] by
      // default, but may be reset using the set_cur() member.  FALSE is
      // returned if type of values does not match type for variable.
      template <class W> bool put( W* vals,
				   size_t c0=0, size_t c1=0, size_t c2=0, size_t c3=0, size_t c4=0 );
    
      // Put n-dimensional arrays, starting at [0, 0, ..., 0] by default,
      // may be reset with set_cur().
      template <class W> bool put( W *vals, const size_t* counts );
    
      // Get scalar or 1, ..., 5 dimensional arrays by providing enough
      // arguments.  Arguments are edge lengths, and their number must not
      // exceed variable's dimensionality.  Start corner is [0,0,..., 0] by
      // default, but may be reset using the set_cur() member.
      template <class W> bool get( W vals, size_t c0=0, size_t c1=0,
				   size_t c2=0, size_t c3=0, size_t c4=0 ) const;
    
      // Get n-dimensional arrays, starting at [0, 0, ..., 0] by default,
      // may be reset with set_cur().
      template <class W> bool get( ncbyte* vals, const size_t* counts ) const;
    
      bool put(void * data);
      /*really think about what these should do, see project to do list*/
      bool setCur(size_t c0=-1, size_t c1=-1, size_t c2=-1,
		  size_t c3=-1, size_t c4=-1);
      bool setCur(size_t* cur);
    
      // these put file in define mode, so could be expensive
      template <class W> NcAtt* addAtt( string name,NcType type, W val );             // add scalar attributes
      template <class W> NcAtt* addAtt(string name, NcUserDefinedType* type,W val);
      // template <class W> NcAtt* addAtt( string, int count,NcType, W val); // vector attributes    //not sure what this should do
      //template <class W> NcAtt* addAtt( string, int count,NcUserDefinedType* type,W val);       //not sure what this should do
      bool rename( string newname );
    
      size_t recSize ( void );             // number of values per record
      size_t recSize ( NcDim* );           // number of values per dimension slice
    
      // Though following are intended for record variables, they also work
      // for other variables, using first dimension as record dimension.
    
      /*do these need to be modified????*/
    
      // Get a record's worth of data
      virtual NcValues *getRec(void);	        // get current record
      virtual NcValues *getRec(size_t rec);        // get specified record
      virtual NcValues *getRec(NcDim* d);        // get current dimension slice
      virtual NcValues *getRec(NcDim* d, size_t slice); // get specified dimension slice
    
      // Put a record's worth of data in current record
      template <class W> bool putRec( W );
    
    
      // Put a dimension slice worth of data in current dimension slice
      template <class W> bool putRec( NcDim* d, W vals );
    
    
      // Put a record's worth of data in specified record  ??
      template <class W> bool putRec( W vals, size_t rec );
    
      // Put a dimension slice worth of data in specified dimension slice
      template <class W> bool putRec( NcDim* d, W vals, size_t slice );
    
    
      // Get first record index corresponding to specified key value(s)
      template <class W> size_t getIndex( W vals );
    
      // Get first index of specified dimension corresponding to key values
      template <class W> size_t getIndex( NcDim* d,const W vals );
    
      // Set current record
      void setRec ( size_t rec );
      // Set current dimension slice
      void setRec ( NcDim* d, size_t slice );
    
      int getId( void ) const;               // variable id
      int getNcId(void);
      /*figure out which of the stuff below should be included.*/
   protected:
      int dimToIndex(NcDim* d);
      size_t* the_cur;
      size_t* cur_rec;
      int myId;
      int myNcId;
      int myGrpId;
      int attCount;
      NcType myType;
      string myName;
      bool valid;
      NcGroup * myGroup;
      // private constructors because only a NcGroup creates these
      NcVar( void );
      //NcVar(NcFile*, int);  not sure if this is ever used
      NcVar(NcGroup * grp,string name,nc_type type,int  ndims,int dimids[]);
      NcVar(NcGroup * grp,string name,nc_type type,int  ndims,int dimids[], int id);
      NcVar(NcGroup * grp,string name,NcUserDefinedType* type);
      int getAttNum( string attname );  // not sure if this has been implemented
      int getNcId()const{return myNcId;}
      string getAttName( int attnum );
      void initCur( void );
      map<string,NcAtt*> myAttributes;
      map<string,NcAtt*>::const_iterator attributeIterator;
      friend class NcGroup;
      friend class NcVar::attIterator;
      friend class NcAtt;
      friend class NcFile;
   };
  
   class NcUserDefinedType  //base class for all userdefined types
   {
   public:
      NcUserDefinedType();
      NcUserDefinedType(string name,int size,NcType type);
      virtual ~NcUserDefinedType();
      virtual void addMember(string memName,NcType type); // virtual function
      virtual void addMember(string memName,NcUserDefinedType* type); //virtual function
      //virtual void commit(); //virtual function
      virtual void addMember(const char * memName,NcType type);
      virtual  void addMember(const char *memName,NcUserDefinedType* type);
      virtual nc_type getType();
      virtual  size_t getSize();
      virtual int getId();
      virtual string getName();
     
   protected:
      size_t mySize;
      ///  int numFields;
      size_t dimCount;
      size_t attCount;
      bool valid;
      string myName; //type name
      nc_type myTypeId;
      nc_type myType;
      NcGroup* myGroup;
    
      friend class NcFile;
   };
  
   class NcCompoundType:public NcUserDefinedType
   {
   public:
      NcCompoundType(NcGroup *,int shape,string name,int id = 0);
      // NcCompoundType(int ncid,int size,string name);
      ~NcCompoundType();
      void addMember(string memName,nc_type type);
      void addMember(const char *memName,NcType type); 
      void addMember(string memName,NcUserDefinedType *type);
      void addMemeber(const char *memName,NcUserDefinedType * type);
      size_t getSize();
      //void commit();
      //accessors
      //	 NcAtts* getAtt( string ) const;       // get a variable attribute by name
   private:
      size_t myOffset;
      size_t myNumFields;
      size_t mySize; 
      //other attributes will come later
      friend class Ncfile;
   };
  
   class NcOpaqueType:public NcUserDefinedType
   {
   public:
      NcOpaqueType(NcGroup *, string name,size_t size,int id = 0);
      ~NcOpaqueType();
      // void addMember(string memName,NcType type);
      // void addMember(string memName,NcUserDefinedType* type);
      size_t getSize();
      //void commit();
      //accessors
      // NcAtt* getAtt( string ) const;       // get a variable attribute by name
   private:
      friend class NcFile;
   };
  
   class NcEnumType:public NcUserDefinedType
   {
   public:
      NcEnumType(NcGroup *, string name,int id = 0);
      ~NcEnumType();
      void addMember(string memName,int value);
      size_t getSize();
      //void commit();
    
   private:
      // string myName; //type name
      friend class NcFile;
    
   };
  
   class NcVLenType:public NcUserDefinedType
   {
   public:
      NcVLenType(NcGroup *, string name,NcType type, int id = 0);
      ~NcVLenType();
      size_t getSize();
             
      friend class NcFile;
   };    
  
  
   class NcException:public exception
   {
   public:
      NcException();
      NcException(string);
      NcException(string,char* file,int line,const char *func);
      NcException(char[]);
      virtual ~NcException() throw();
      virtual void what()
      {
	 cout<<fileName<<":"<<lnumber<<" "<<"from method "<<funcName<<" "<<message<<endl;
      }
   private:
      string message;   //error mesasge
      string funcName;  //function where the error occurs
      string fileName;  //file containing the error
      int lnumber;          //line number where the error occurs
   };
  
  
   //the following structures are used for comparitors with maps used for storage
  
   struct dimCmp
   {
      bool operator()(NcDim * par1, NcDim * par2) const
      {
	 return par1->getId()< par2->getId();
      }
   };
   struct attCmp
   {
      bool operator()(NcAtt * par1, NcAtt * par2) const
      {
	 return par1->getId()< par2->getId();
      }
   };
  
   struct varCmp
   {
      bool operator()(NcVar* par1, NcVar * par2) const
      {
	 return par1->getId()< par2->getId();
      }
   };
   struct grpCmp
   {
      bool operator()(NcGroup * par1, NcGroup * par2) const
      {
	 return par1->getId()< par2->getId();
      }
   };
   
   class NcValues
   {
   public:
      ~NcValues();  //frees all allocated memory      
   
      //accessors
      size_t getNum();   //these two methods may do the same thing
      size_t getSize();  //these two methods may do the same thing
      float* getData();
      ostream& print(ostream&)const;
      ncbyte toNcByte(size_t n);
      char toChar(size_t n);
      short toShort(size_t n);
      int toInt(size_t n);
      nclong toNcLong(size_t n);
      long toLong(size_t n);
      string toString();

      //overloaded operators
      NcValues& operator=(NcValues & rhs);
      bool operator==(NcValues & rhs);
      //this covers stuff for those who prefer access via fortran methods..
      //should I also include theoperator[]()  for those who prefer the c/c++ style of direct access
     
      /*Should these be included???*/
      // I'm not sure if this syntax is allowed
      // similar to accessing an index of an array by saying array[i0][i1][i2][i3][i4]
      //float& operator()(size_t i0,size_t i1,size_t i2,size_t i3,size_t i4);
     
      // I think the syntax below is correct
      // float& operator[](size_t i0);  //allows direct access to a one dimensional portion of an array
     
   private:
      float * myData;
      NcVar * myVariable;
      NcType myType;
      NcValues();  //disable the default constructor
      NcValues(NcVar * var);
      friend class NcVar;
   };  
  

  
   template<class G> NcAtt::NcAtt(NcVar* var,string name,NcType type,G val)
      {
	 int status;
	 myVariable=var;
	 myName= name;
	 myNcId= var->getId();
	 if(type ==2||type == 12)
	    {
	       stringstream  myStream;  
	       myStream << val;
	       myStream >> myValue;
	    }
	 else
	    {
	       myValue = "nonString Convertable";
	    }
	 int size = 1;  //set to 1 so that extra's aren't allocated and filled in

	 if(!var->isReadOnlyMode())
	    {
	       status =  nc_put_att(var->getNcId(),var->getId(),name.c_str(),(nc_type)type,size,&val);
	 
	       if( status)
		  throw NcException(nc_strerror(status),__FILE__,__LINE__,__FUNCTION__);
	    }
      
      }
   
   template<class G> NcAtt::NcAtt(NcGroup* grp,string name,NcUserDefinedType* type,G val )
      {  
	 int status;
	 myGroup = grp;
	 myName = name;
	 myNcId = grp->getId();

	 myValue = "nonString Convertable";

	 int size = 1;
      
	 if(!grp->isReadOnlyMode())
	    {
	       status =  nc_put_att(grp->getNcId(),NC_GLOBAL,name.c_str(),type->getType(),size,&val); 
	       if( status) 
		  throw NcException(nc_strerror(status),__FILE__,__LINE__,__FUNCTION__);
	    }
      }

   template<class G> NcAtt::NcAtt(NcGroup* grp,string name,NcType type,G val )
      { 
	 int status;
	 myGroup = grp;
	 myName = name;
	 myNcId = grp->getId();
	 int size = 1;
	 if(type == 2 || type == 12)
	    {
	       stringstream  myStream;  
	       myStream << val;
	       myStream >> myValue;
	    }
	 else
	    {
	       myValue = "nonString Convertable";
	    }

	 if(!grp->isReadOnlyMode())
	    {
	       status =  nc_put_att(grp->getNcId(),NC_GLOBAL,name.c_str(),type,size,&val); 
	       if( status) 
		  throw NcException(nc_strerror(status),__FILE__,__LINE__,__FUNCTION__);
	    }
      }


   template < class T > NcAtt * NcGroup::addAtt(string attName,NcType type,T value)
      {
	 NcAtt * att = new NcAtt(this,attName,type,value);
	 myAttributes.insert(make_pair(attName,att));
	 attCount++;
	 return att;
      }

   template < class T > NcAtt * NcGroup::addAtt(string attName,NcUserDefinedType* type,T value)
      {
	 NcAtt * att = new NcAtt(this,attName,type,value);
	 myAttributes.insert(make_pair(attName,att));
	 attCount++;
	 return att;
      }



   template <class W> 
      bool NcVar::put( W* vals,size_t c0, size_t c1, size_t c2, size_t c3, size_t c4 )
    
      // Put n-dimensional arrays, starting at [0, 0, ..., 0] by default,
      // may be reset with set_cur().
      {
	 size_t start[]={0,0,0,0,0};
	 size_t count[]={c0,c1,c2,c3,c4};
	 int ret;
	 //    if(c0 == 1)	
      
	 if(c0)
	    {
	       if((ret== nc_put_vara(myNcId,myId,start,count,vals)))
		  throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	    }
	 else
	    {
	       //  if((ret== nc_put_var1_int(myNcId,myId,0,vals)))
	       //throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
	    }
	       
      }
      
   template <class W> 

      bool NcVar::put( W* vals, const size_t* count )
    
      // Get scalar or 1, ..., 5 dimensional arrays by providing enough
      // arguments.  Arguments are edge lengths, and their number must not
      // exceed variable's dimensionality.  Start corner is [0,0,..., 0] by
      // default, but may be reset using the set_cur() member.
      {

	 int ret;
	 size_t start[getNumDims()];
	 for (int i = 0; i < getNumDims(); i++)
	    start[i] = the_cur[i];

	 if((ret = nc_put_vara(myNcId, myId, start,count, vals))) 
	    throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__);
      }



   template <class W>
      bool NcVar::get( W vals, size_t c0, size_t c1,
		       size_t c2, size_t c3, size_t c4 ) const
    
      // Get n-dimensional arrays, starting at [0, 0, ..., 0] by default,
      // may be reset with set_cur().
      {
	 long count[5];							      
	 count[0] = c0;							      
	 count[1] = c1;							      
	 count[2] = c2;							      
	 count[3] = c3;							      
	 count[4] = c4;							      
	 for (int i = 0; i < getNumDims(); i++)
	    {	
	       if (count[i])
		  {	
		     if (getNumDims() < i)						      
			return false;						      
		  }
	    }	
      
	 long start[getNumDims()];
            
	 for (int j = 0; j < getNumDims(); j++) 
	    { 					      
	       start[j] = the_cur[j];
	    }		
      
	 int ret;
	 if(ret = ncvarget(myNcId,myId, start, count, vals))
	    throw NcException(nc_strerror(ret),__FILE__,__LINE__,__FUNCTION__); 
	 return (ret == 0);  // true if all is well
      }
   
   template <class W> 
      bool NcVar::get( ncbyte* vals, const size_t* counts ) const
      {   				      
	 long start[MAX_NC_DIMS];						      
	 for (int i = 0; i < getNumDims(); i++)				      
	    start[i] = the_cur[i];						      
	 return ncvarget(myNcId,myId, start, counts, vals) != NC_NOERR;       
      }
   
   // these put file in define mode, so could be expensive
   template <class W> NcAtt *  NcVar::addAtt( string attName,NcType type, W value )             // add scalar attributes
      { 
	 NcAtt * att = new NcAtt(this,attName,type,value);
	 myAttributes.insert(pair<string,NcAtt*>(attName,att));
	 attCount++;
	 return att;
      }

   template <class W> NcAtt* NcVar::addAtt(string attName, NcUserDefinedType* type,W value)
      {
	 NcAtt *att = new NcAtt(this,attName,type,value);
	 myAttributes.insert(pair<string,NcAtt*>(attName,att));
	 attCount++;
	 return att;
    
      }

  
   template <class T> NcAtt* NcFile::addAtt(string attName,NcType type,T value)
      {
	 return myRootGroup->addAtt(attName,type,value);
      }


  
   /* template <class W>
      NcAtt* NcVar::addAtt( string name, int count,NcType type, W val) // vector attributes  // I'm not sure what this should do
      {
	 cout<<"add att with 4 parameters (string, int,NcType, W) has not been implemented yet in netcdfcpp4.h"<<endl; 
      
	 return false;
      }

   template <class W>
      NcAtt* NcVar::addAtt( string name, int count,NcUserDefinedType* type, W val) // vector attributes   //I'm not sure what this should do
      {
	 cout<<"add att with 4 parameters (string, int,NcUserDefinedType, W) has not been implemented yet in netcdfcpp4.h"<<endl; 

      
	 return false;
      }
   */
  
   // Put a record's worth of data in current record
   template <class W> bool NcVar::putRec( W vals)
      {   
	 return putRec(getDim(0), vals, cur_rec[0]); 
      }
  
  
   // Put a dimension slice worth of data in current dimension slice
   template <class W> bool NcVar::putRec( NcDim* d, W vals )
      { 
	 int idx = dimToIndex(d);		
	 return putRec(d, vals, cur_rec[idx]);
      }
  
  
   // Put a record's worth of data in specified record  ??
   template <class W> bool NcVar::putRec( W vals, size_t rec )
      {
	 
	 NcDim* t = getDim(0);
	 return putRec(t, vals, rec);
      }
  
   // Put a dimension slice worth of data in specified dimension slice
   template <class W> bool NcVar::putRec( NcDim* d, W vals, size_t slice )
      {
	 int idx = dimToIndex(d);
	 size_t size = getNumDims();                                                   
	 size_t* start = new size_t[size];                                             
	 for (int i = 1; i < size ; i++) 
	    start[i] = 0;                               
	 start[idx] = slice;   
	 bool result = setCur(start);                                           
	 delete [] start;                                                          
	 if (! result )                                                            
	    return false;
                                                          
	 size_t* edge = edges();                                                     
	 edge[idx] = 1; 
              
	 result = put(vals, edge);        
                                         
	 delete [] edge;                                                           
	 return result;             
      }
   
   
   // Get first record index corresponding to specified key value(s)
   template <class W> size_t NcVar::getIndex( W key )
      {
	 return getIndex(getDim(0), key); 
      }
   
   // Get first index of specified dimension corresponding to key values
   template <class W> size_t NcVar::getIndex( NcDim* d,const W vals )
      {
	 cout<<"NcVar::getIndex has not been implemented yet"<<endl;
	 //    return get_index(get_dim(0),vals);  //not sure if this is correct
       
	 //I'm not sure what should go here yet
	 /*
	   if (type() != NcTypeEnum(TYPE))                                               
	   return -1;                                                                
	   if (! the_file->data_mode())                                                  
	   return -1;                                                                
	   int idx = dim_to_index(rdim);                                                 
	   long maxrec = get_dim(idx)->size();                                           
	   long maxvals = rec_size(rdim);                                                
	   NcValues* val;                                                                
	   int validx;                                                                   
	   for (long j=0; j<maxrec; j++) 
	   {                                               
	   val = get_rec(rdim,j);                                                    
	   if (val == NULL) return -1;                                               
	   for (validx = 0; validx < maxvals; validx++) 
	   {                            
	   if (key[validx] != val->as_ ## TYPE(validx)) break;                   
	   }                                                                     
	   delete val;                                                               
	   if (validx == maxvals) return j;                                          
	   }*/                                                                         
	 return -1;                     
      }
}

 
#endif

