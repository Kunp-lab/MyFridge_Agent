# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_test_pk_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED test_pk_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(test_pk_FOUND FALSE)
  elseif(NOT test_pk_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(test_pk_FOUND FALSE)
  endif()
  return()
endif()
set(_test_pk_CONFIG_INCLUDED TRUE)

# output package information
if(NOT test_pk_FIND_QUIETLY)
  message(STATUS "Found test_pk: 0.0.0 (${test_pk_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'test_pk' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${test_pk_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(test_pk_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${test_pk_DIR}/${_extra}")
endforeach()
