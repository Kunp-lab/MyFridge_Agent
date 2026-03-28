#if !defined(__USB_CAM_USB_CAM_HPP__)
#define __USB_CAM_USB_CAM_HPP__
extern "C"
{
#include <libavcodec/avcodec.h>
#include <linux/videodev2.h>
}

#include <string>
#include <vector>

namespace usb_cam
{

struct capture_format_t
{
    struct v4l2_fmtdesc;
    struct v4l2_frmivalenum;
};

struct set_para_t
{
    // path or name para
    std::string camera_name;
    std::string device_name;
    std::string frame_id;
    std::string camera_info_url;
    std::string camera_calibration_file_path;
    std::string io_method_name;
    std::string pixel_format_name;
    std::string av_device_format;

    // format
    int image_width;
    int image_height;
    int framerate;

    // image para
    int brightness;
    int contrast;
    int saturation;
    int sharpness;
    int gain;
    int white_balance;
    int exposure;
    int focus;
    bool auto_white_balance;
    bool autoexposure;
    bool autofocus;

    // other
    bool zero_copy;
};

struct image_t
{
};

class UsbCam
{
  public:
    UsbCam();
    ~UsbCam();
    std::vector<capture_format_t> get_supported_formats();

    void configure(set_para_t para);

    void start();

    void shutdown();

    void get_image(char *data);

    char *get_image();

  private:
    std::vector<capture_format_t> supported_formats;
    void init_device();

    void open_device();
    void close_device();
    void configure_device();
    void uninit_device();
};

} // namespace usb_cam

#endif // __USB_CAM_USB_CAM_HPP__
