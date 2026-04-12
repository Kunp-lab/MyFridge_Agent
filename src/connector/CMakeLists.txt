cmake_minimum_required(VERSION 3.5)
project(connector)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 20)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(OpenCV REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

add_executable(mcu_connector_node src/mcu_connector_node.cpp)
add_executable(qdriver_connector_node src/qdriver_connector_node.cpp)

target_include_directories(mcu_connector_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(
  mcu_connector_node
  "rclcpp"
  "std_msgs"
  "sensor_msgs"
)

target_include_directories(qdriver_connector_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(
  qdriver_connector_node
  "ament_index_cpp"
  "rclcpp"
  "std_msgs"
  "sensor_msgs"
)
target_include_directories(qdriver_connector_node PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(qdriver_connector_node ${OpenCV_LIBS})

install(TARGETS mcu_connector_node
  DESTINATION lib/${PROJECT_NAME})
  
install(TARGETS qdriver_connector_node
  DESTINATION lib/${PROJECT_NAME})

install(FILES assets/haarcascade_frontalface_default.xml
  DESTINATION share/${PROJECT_NAME}/assets)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
