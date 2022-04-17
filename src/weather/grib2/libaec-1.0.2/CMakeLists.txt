cmake_minimum_required(VERSION 3.1)
set(CMAKE_C_STANDARD 99)
include(CheckIncludeFiles)
include(TestBigEndian)
include(CheckCSourceCompiles)
include(CheckSymbolExists)
include(cmake/macros.cmake)
project(libaec)
set(libaec_VERSION_MAJOR 1)
set(libaec_VERSION_MINOR 0)
set(libaec_VERSION_PATCH 2)
set(CMAKE_BUILD_TYPE Release)
enable_testing()

check_include_files(malloc.h HAVE_MALLOC_H)
check_include_files(stdint.h HAVE_STDINT_H)
test_big_endian(WORDS_BIGENDIAN)
check_clzll(HAVE_DECL___BUILTIN_CLZLL)
if(NOT HAVE_DECL___BUILTIN_CLZLL)
  check_bsr64(HAVE_BSR64)
endif(NOT HAVE_DECL___BUILTIN_CLZLL)
find_inline_keyword()
find_restrict_keyword()

check_symbol_exists(snprintf "stdio.h" HAVE_SNPRINTF)
if(NOT HAVE_SNPRINTF)
  check_symbol_exists(_snprintf "stdio.h" HAVE__SNPRINTF)
  check_symbol_exists(_snprintf_s "stdio.h" HAVE__SNPRINTF_S)
endif(NOT HAVE_SNPRINTF)

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/config.h.in
  ${CMAKE_CURRENT_BINARY_DIR}/config.h)
add_definitions("-DHAVE_CONFIG_H")

option(BUILD_SHARED_LIBS "Build Shared Libraries" ON)
if(BUILD_SHARED_LIBS)
  set (LIB_TYPE SHARED)
else(BUILD_SHARED_LIBS)
  if(WIN32)
    message(WARNING "You will have to modify libaec.h for static libs.")
  endif(WIN32)
  set(LIB_TYPE STATIC)
endif(BUILD_SHARED_LIBS)

set(libaec_SRCS
  ${PROJECT_SOURCE_DIR}/src/encode.c
  ${PROJECT_SOURCE_DIR}/src/encode_accessors.c
  ${PROJECT_SOURCE_DIR}/src/decode.c)

include_directories("${PROJECT_BINARY_DIR}")
include_directories("${PROJECT_SOURCE_DIR}/src")

add_subdirectory(src)
add_subdirectory(tests)

option(AEC_FUZZING "Enable build of fuzzing targets" OFF)
if(AEC_FUZZING)
  add_subdirectory(fuzzing)
endif()

set(CPACK_PACKAGE_NAME "libaec")
set(CPACK_PACKAGE_VENDOR "Deutsches Klimarechenzentrum GmbH")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY
  "libaec - Adaptive Entropy Coding library")
set(CPACK_PACKAGE_VERSION_MAJOR "${libaec_VERSION_MAJOR}")
set(CPACK_PACKAGE_VERSION_MINOR "${libaec_VERSION_MINOR}")
set(CPACK_PACKAGE_VERSION_PATCH "${libaec_VERSION_PATCH}")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "libaec")
set(CPACK_RESOURCE_FILE_LICENSE "${PROJECT_SOURCE_DIR}/Copyright.txt")

if(WIN32)
  set(CPACK_GENERATOR "WIX")
  set(CPACK_WIX_UPGRADE_GUID "E58A21F6-BB99-46B5-8AD8-6114E4CCA0A6")
  if(CMAKE_CL_64)
    set(CPACK_INSTALL_DIRECTORY "$PROGRAMFILES64")
    set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY
      "${CPACK_PACKAGE_NAME}-${CPACK_PACKAGE_VERSION} (Win64)")
  else(CMAKE_CL_64)
    set(CPACK_INSTALL_DIRECTORY "$PROGRAMFILES")
    set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY
      "${CPACK_PACKAGE_NAME}-${CPACK_PACKAGE_VERSION}")
  endif(CMAKE_CL_64)
endif(WIN32)

include(CPack)
