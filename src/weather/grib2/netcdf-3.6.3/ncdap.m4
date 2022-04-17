AC_DEFUN([NCDAP_XML2], [dnl
  # Did user must specify a location for the XML2 library?
  AC_MSG_CHECKING([whether a location for the XML2 library was specified])
  AC_ARG_WITH([xml2], [AS_HELP_STRING([--with-xml2=<directory>],
              [Specify location of XML2 library. XML2 is required for opendap. Configure will expect to find subdirs include and lib.])],
              [xml2dir=$with_xml2])
  AC_MSG_RESULT([$with_xml2])
  if test -z "${with_xml2}" ; then
    # Not specified, see if autoconf can find it
    AC_CHECK_LIB([xml2],[xmlParseFile],[found_xml2=1],[found_xml2=])
  else
    found_xml2=1
  fi
  if test -z "${found_xml2}" ; then
    AC_MSG_WARN([xml2 library not found])
  fi
  xml2_libs="-lxml2"
  if test -n "${xml2dir}" ; then
    xml2_cppflags="-I${xml2dir}/include"
    xml2_libs="-L${xml2dir}/lib ${xml2_libs}"
  fi
  AC_SUBST([XML2_CPPFLAGS],[${xml2_cppflags}])
  AC_SUBST([XML2_LIBS],[${xml2_libs}])
  AC_SUBST([XML2DIR],[${xml2dir}])
  AM_CONDITIONAL(USE_XML2_DIR, [test "x${xml2dir}" != "x"])
  # See if we can locate xml2-config; if so, then use it
  if ! `type xml2-config &>/dev/null` ; then
    AC_MSG_WARN([Cannot check libxml2 version])
  else
    version_libxml2=`xml2-config --version`  
    dnl Test for several different versions of libxml2. We can use 2.5.7   
    dnl or newer, but part of the SAX interface changes depending on the  
    dnl version.  
    version_M=`echo $version_libxml2|cut -d ' ' -f2 |cut -d '.' -f1`  
    version_m=`echo $version_libxml2|cut -d ' ' -f2 |cut -d '.' -f2`  
    version_m_m=`echo $version_libxml2|cut -d ' ' -f2 |cut -d '.' -f3`  
    # ugh!  
    ok=  
    if test "$version_M" -gt 2 ; then  
      ok=1  
    elif test "$version_M" == 2 ; then  
      if test "$version_m" -gt 5 ; then  
        ok=1  
      elif test "$version_m" == 5 ; then  
        if test "$version_m_m" -ge 7 ; then ok=1; fi  
      fi  
    fi  
    if ! test ok ; then  
        AC_MSG_ERROR([must have libxml2 2.5.7 or greater, found $version_libxml2])  
    fi  
    dnl Sort out the particular variant  
    if test $version_M -eq 2 && test $version_m -eq 5 && test $version_m_m -ge 10  
    then  
        AC_DEFINE(LIBXML2_5_10, [1], [define if you have xml2 2.5.10 or greater])  
    fi  
    if test $version_M -eq 2 && test $version_m -eq 6 && test $version_m_m -ge 16  
    then  
        AC_DEFINE(LIBXML2_5_10, [1], [define if you have xml2 2.5.10 or greater])  
        AC_DEFINE(LIBXML2_6_16, [1], [define if you have xml2 2.6.16 or greater])  
    fi  
    XML2_CFLAGS="`xml2-config --cflags`"  
    AC_SUBST([XML2_CFLAGS])  
  fi
])  
AC_DEFUN([NCDAP_CURL], [dnl
  # Did user must specify a location for the CURL library?
  AC_MSG_CHECKING([whether a location for the CURL library was specified])
  AC_ARG_WITH([curl], [AS_HELP_STRING([--with-curl=<directory>],
              [Specify location of CURL library. CURL is required for opendap. Configure will expect to find subdirs include and lib.])],
              [curldir=$with_curl])
  AC_MSG_RESULT([$with_curl])
  if test -z "${with_curl}" ; then
    # Not specified, see if autoconf can find it
    AC_CHECK_LIB([curl],[curl_easy_setopt],[found_curl=1],[found_curl=])
  else
    found_curl=1
  fi
  if test -z "${found_curl}" ; then
    AC_MSG_WARN([curl library not found])
  fi
  curl_libs="-lcurl"
  if test -n "${curldir}" ; then
    curl_cppflags="-I${curldir}/include"
    curl_libs="-L${curldir}/lib ${curl_libs}"
  fi
  AC_SUBST([CURL_CPPFLAGS],[${curl_cppflags}])
  AC_SUBST([CURL_LIBS],[${curl_libs}])
  AC_SUBST([CURLDIR],[${curldir}])
  AM_CONDITIONAL(USE_CURL_DIR, [test "x${curldir}" != "x"])
  # See if we can locate curl-config; if so, then use it to check version
  if ! `type curl-config &>/dev/null` ; then
    AC_MSG_WARN([Cannot check libcurl version])
  else
    version_libcurl=`curl-config --version`
    version_M=`echo $version_libcurl|cut -d ' ' -f2 |cut -d '.' -f1`
    version_m=`echo $version_libcurl|cut -d ' ' -f2 |cut -d '.' -f2`
    version_m_m=`echo $version_libcurl|cut -d ' ' -f2 |cut -d '.' -f3`
    # ugh!
    ok=
    if test "$version_M" -gt 7 ; then
      ok=1
    elif test "$version_M" == 7 ; then
      if test "$version_m" -gt 10 ; then
        ok=1
      elif test "$version_m" == 10 ; then
        if test "$version_m_m" -ge 6 ; then ok=1; fi
      fi
    fi
    if ! test ok ; then
      AC_MSG_ERROR([must have libcurl 7.10.6 or greater, found $version_libcurl])
    fi
    CURL_CFLAGS="`curl-config --cflags`"
    AC_SUBST([CURL_CFLAGS])
  fi
])
AC_DEFUN([NCDAP_ZLIB], [dnl
  # Did user must specify a location for the ZLIB library?
  AC_MSG_CHECKING([whether a location for the ZLIB library was specified])
  AC_ARG_WITH([zlib], [AS_HELP_STRING([--with-zlib=<directory>],
              [Specify location of ZLIB library. ZLIB is required for opendap. Configure will expect to find subdirs include and lib.])],
              [zlibdir=$with_zlib])
  AC_MSG_RESULT([$with_zlib])
  if test -z "${with_zlib}" ; then
    # Not specified, see if autoconf can find it
    AC_CHECK_LIB([z],[zlibVersion],[found_zlib=1],[found_zlib=])
  else
    found_zlib=1
  fi
  if test -z "${found_zlib}" ; then
    AC_MSG_WARN([z library not found])
  fi
  zlib_libs="-lz"
  if test -n "${zlibdir}" ; then
    zlib_cppflags="-I${zlibdir}/include"
    zlib_libs="-L${zlibdir}/lib ${zlib_libs}"
  fi
  AC_SUBST([ZLIB_CPPFLAGS],[${zlib_cppflags}])
  AC_SUBST([ZLIB_LIBS],[${zlib_libs}])
  AC_SUBST([ZLIBDIR],[${zlibdir}])
  AM_CONDITIONAL(USE_ZLIB_DIR, [test "x${zlibdir}" != "x"])
])

AC_DEFUN([NCDAP_SZLIB], [dnl
  # Did user must specify a location for the SZLIB library?
  AC_MSG_CHECKING([whether a location for the SZLIB library was specified])
  AC_ARG_WITH([szlib], [AS_HELP_STRING([--with-szlib=<directory>],
              [Specify location of SZLIB library. SZLIB MAY be required for opendap if either xml2 or curl require it. Configure will expect to find subdirs include and lib.])],
              [szlibdir=$with_szlib])
  AC_MSG_RESULT([$with_szlib])
  if test -z "${with_szlib}" ; then
    # Not specified, see if autoconf can find it
    AC_CHECK_LIB([sz],[SZ_Decompress],[found_szlib=1],[found_szlib=])
  else
    found_szlib=1
  fi
  if test -z "${found_szlib}" ; then
    AC_MSG_WARN([sz library not found])
  fi
  szlib_libs="-lsz"
  if test -n "${szlibdir}" ; then
    szlib_cppflags="-I${szlibdir}/include"
    szlib_libs="-L${szlibdir}/lib ${szlib_libs}"
  fi
  AC_SUBST([SZLIB_CPPFLAGS],[${szlib_cppflags}])
  AC_SUBST([SZLIB_LIBS],[${szlib_libs}])
  AC_SUBST([SZLIBDIR],[${szlibdir}])
  AM_CONDITIONAL(USE_SZLIB_DIR, [test "x${szlibdir}" != "x"])
])

