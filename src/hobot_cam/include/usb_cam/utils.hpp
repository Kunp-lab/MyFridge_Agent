#if !defined(__USB_CAM_UTILS_HPP__)
#define __USB_CAM_UTILS_HPP__

extern "C"
{
#include <fcntl.h>
#include <linux/videodev2.h>
}

#include <ctime>
#include <map>
#include <unistd.h>

namespace usb_cam
{
namespace utils
{

// using usb_cam::formats::pixel_format_base;

typedef enum
{

} io_method_t;

struct buffer
{
    /* data */
};

inline time_t get_epoch_time_shift_us() {}

inline timespec calc_img_timestamp(const timeval &buffer_time,
                                   const time_t &epoch_time_shift_us)
{
}

inline int xioctl(int fd, __uint64_t request, void *arg) {}

inline io_method_t io_method_from_string(const std::string &str) {}

inline std::map<std::string, v4l2_capability> available_devices() {}

} // namespace utils

} // namespace usb_cam

#endif // __USB_CAM_UTILS_HPP__
