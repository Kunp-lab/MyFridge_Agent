# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_websocket_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED websocket_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(websocket_FOUND FALSE)
  elseif(NOT websocket_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(websocket_FOUND FALSE)
  endif()
  return()
endif()
set(_websocket_CONFIG_INCLUDED TRUE)

# output package information
if(NOT websocket_FIND_QUIETLY)
  message(STATUS "Found websocket: 2.3.3 (${websocket_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'websocket' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${websocket_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(websocket_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${websocket_DIR}/${_extra}")
endforeach()
