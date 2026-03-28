// #include <linux/v>

/*

打开设备
更改设备属性，选择视频和音频输入，视频标准，图片亮度等
设置数据格式
设置输入/输出方法
输入/输出缓存队列循环
关闭设备


*/

extern "C"
{
#include <linux/videodev2.h>
#include <sys/fcntl.h>
#include <sys/unistd.h>
}
#include <fstream>

int main(int argc, char const *argv[])
{
    /* code */
    // v4l2_input
    const char *dev_name = "/dev/video0";
    int fd = open(dev_name, O_RDWR | O_NONBLOCK);
    if (-1 == fd)
    {
        printf("ERR(%s):failed to open %s\n", __func__, dev_name);
        return -1;
    }

    struct v4l2_capability cap;

    int i = close(fd);
    return 0;
}
