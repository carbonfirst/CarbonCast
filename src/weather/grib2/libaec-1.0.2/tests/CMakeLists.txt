add_library(check_aec STATIC check_aec.c)

add_executable(check_code_options check_code_options.c)
target_link_libraries(check_code_options check_aec aec)
add_test(NAME check_code_options COMMAND check_code_options)
add_executable(check_buffer_sizes check_buffer_sizes.c)
target_link_libraries(check_buffer_sizes check_aec aec)
add_test(NAME check_buffer_sizes COMMAND check_buffer_sizes)
add_executable(check_long_fs check_long_fs.c)
target_link_libraries(check_long_fs check_aec aec)
add_test(NAME check_long_fs COMMAND check_long_fs)
add_executable(check_szcomp check_szcomp.c)
target_link_libraries(check_szcomp check_aec sz)
add_test(NAME check_szcomp
  COMMAND check_szcomp ${PROJECT_SOURCE_DIR}/data/121B2TestData/ExtendedParameters/sar32bit.dat)

if(UNIX)
  add_test(
    NAME sampledata.sh
    COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/sampledata.sh ${CMAKE_CURRENT_SOURCE_DIR}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endif(UNIX)
