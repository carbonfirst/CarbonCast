macro(check_clzll VARIABLE)
  check_c_source_compiles(
    "int main(int argc, char *argv[])
{return __builtin_clzll(1LL);}"
    ${VARIABLE}
    )
endmacro()

macro(check_bsr64 VARIABLE)
  check_c_source_compiles(
    "int main(int argc, char *argv[])
{unsigned long foo; unsigned __int64 bar=1LL;
return _BitScanReverse64(&foo, bar);}"
    ${VARIABLE}
    )
endmacro()

macro(find_inline_keyword)
  #Inspired from http://www.cmake.org/Wiki/CMakeTestInline
  set(INLINE_TEST_SRC "/* Inspired by autoconf's c.m4 */
static inline int static_foo(){return 0\;}
int main(int argc, char *argv[]){return 0\;}
")
  file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/CMakeTestCInline.c
    ${INLINE_TEST_SRC})

  foreach(KEYWORD "inline" "__inline__" "__inline")
    if(NOT DEFINED C_INLINE)
      try_compile(C_HAS_${KEYWORD}
        ${CMAKE_CURRENT_BINARY_DIR}
        ${CMAKE_CURRENT_BINARY_DIR}/CMakeTestCInline.c
        COMPILE_DEFINITIONS "-Dinline=${KEYWORD}"
        )
      if(C_HAS_${KEYWORD})
        set(C_INLINE TRUE)
        add_definitions("-Dinline=${KEYWORD}")
        message(STATUS "Inline keyword found - ${KEYWORD}")
      endif(C_HAS_${KEYWORD})
    endif(NOT DEFINED C_INLINE)
  endforeach(KEYWORD)

  if(NOT DEFINED C_INLINE)
    add_definitions("-Dinline=")
    message(STATUS "Inline keyword - not found")
  endif(NOT DEFINED C_INLINE)
endmacro(find_inline_keyword)

macro(find_restrict_keyword)
  set(RESTRICT_TEST_SRC "/* Inspired by autoconf's c.m4 */
int foo (int * restrict ip){return ip[0]\;}
int main(int argc, char *argv[]){int s[1]\;
int * restrict t = s\; t[0] = 0\; return foo(t)\;}
")

  file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/CMakeTestCRestrict.c
    ${RESTRICT_TEST_SRC})

  foreach(KEYWORD "restrict" "__restrict" "__restrict__" "_Restrict")
    if(NOT DEFINED C_RESTRICT)
      try_compile(C_HAS_${KEYWORD}
        ${CMAKE_CURRENT_BINARY_DIR}
        ${CMAKE_CURRENT_BINARY_DIR}/CMakeTestCRestrict.c
        COMPILE_DEFINITIONS "-Drestrict=${KEYWORD}"
        )
      if(C_HAS_${KEYWORD})
        set(C_RESTRICT TRUE)
        add_definitions("-Drestrict=${KEYWORD}")
        message(STATUS "Restrict keyword found - ${KEYWORD}")
      endif(C_HAS_${KEYWORD})
    endif(NOT DEFINED C_RESTRICT)
  endforeach(KEYWORD)

  if(NOT DEFINED C_RESTRICT)
    add_definitions("-Drestrict=")
    message(STATUS "Restrict keyword - not found")
  endif(NOT DEFINED C_RESTRICT)
endmacro(find_restrict_keyword)
