add_library(aec ${LIB_TYPE} ${libaec_SRCS})
set_target_properties(aec PROPERTIES VERSION 0.0.8 SOVERSION 0)
add_library(sz ${LIB_TYPE} sz_compat.c)
set_target_properties(sz PROPERTIES VERSION 2.0.1 SOVERSION 2)

target_link_libraries(sz aec)
if(WIN32 AND BUILD_SHARED_LIBS)
  set_target_properties (aec PROPERTIES DEFINE_SYMBOL "BUILDING_LIBAEC")
  set_target_properties (sz PROPERTIES DEFINE_SYMBOL "BUILDING_LIBAEC")
  set_target_properties(sz PROPERTIES OUTPUT_NAME "szip")
endif(WIN32 AND BUILD_SHARED_LIBS)

add_executable(aec_client aec.c)
set_target_properties(aec_client PROPERTIES OUTPUT_NAME "aec")
target_link_libraries(aec_client aec)

if(UNIX)
  add_executable(utime EXCLUDE_FROM_ALL utime.c)
  add_custom_target(bench
    COMMAND ${CMAKE_SOURCE_DIR}/src/benc.sh ${CMAKE_SOURCE_DIR}/data/typical.rz
    COMMAND ${CMAKE_SOURCE_DIR}/src/bdec.sh
    DEPENDS aec_client utime)
endif(UNIX)

include(GNUInstallDirs)
if(WIN32)
  install(TARGETS aec sz
    RUNTIME
    DESTINATION bin
    ARCHIVE
    DESTINATION lib
    COMPONENT libraries)
else(WIN32)
  install(TARGETS aec sz
    LIBRARY
    DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE
    DESTINATION ${CMAKE_INSTALL_LIBDIR}
    COMPONENT libraries)
  install(FILES aec.1
    DESTINATION ${CMAKE_INSTALL_FULL_MANDIR}/man1 COMPONENT doc)
endif(WIN32)

install(FILES libaec.h szlib.h
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
  COMPONENT headers)
install(TARGETS aec_client
  RUNTIME
  DESTINATION ${CMAKE_INSTALL_BINDIR}
  COMPONENT applications)

set(CPACK_COMPONENTS_ALL applications libraries headers doc)
