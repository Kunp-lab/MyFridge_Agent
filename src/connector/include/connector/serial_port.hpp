#include <atomic>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <termios.h>
#include <thread>
#include <unistd.h>
#include <vector>

class SerialPort
{
  public:
    SerialPort(std::string device, int speed)
        : fd_(-1), is_open_(false), speed_(speed), device_(device),
          running_(false)
    {
    }

    ~SerialPort()
    {
        if (is_open_)
        {
            shutdown();
        }
    }

    void
    setDefaultHandler(std::function<void(const std::vector<uint8_t> &)> handler)
    {
        callback_ = handler;
    }

    void setProtocolParser(
        std::function<std::vector<uint8_t>(const std::vector<uint8_t> &)>
            parser)
    {
        protocol_parser_ = parser;
    }

    void setRxFrameFormat(const std::vector<uint8_t> &header,
                          const std::vector<uint8_t> &tail,
                          size_t min_payload_size = 0)
    {
        frame_header_ = header;
        frame_tail_ = tail;
        frame_min_payload_size_ = min_payload_size;
    }

    void setTxFrameFormat(const std::vector<uint8_t> &header,
                          const std::vector<uint8_t> &tail)
    {
        send_frame_header_ = header;
        send_frame_tail_ = tail;
    }

    void setFunctionCodePosition(size_t offset)
    {
        function_code_offset_ = offset;
    }

    void addFunctionHandler(
        uint8_t func_code,
        std::function<void(const std::vector<uint8_t> &)> handler)
    {
        function_handlers_[func_code] = handler;
    }

    bool init()
    {
        if (is_open_)
        {
            throw std::runtime_error("device has been opened\n");
        }

        fd_ = ::open(device_.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
        if (fd_ == -1)
        {
            throw std::runtime_error("Failed to open serial port: " + device_);
        }

        // Save original settings
        if (tcgetattr(fd_, &old_tio_) != 0)
        {
            ::close(fd_);
            throw std::runtime_error("Failed to get terminal attributes");
        }

        // Configure and set speed
        configureTermios();
        setBaudRate(speed_);

        is_open_ = true;

        // Start read thread only if callback is set
        if (callback_)
        {
            running_ = true;
            read_thread_ = std::thread(&SerialPort::readLoop, this);
        }

        return true;
    }

    bool shutdown()
    {
        if (!is_open_)
            return true;

        running_ = false;
        if (read_thread_.joinable())
        {
            read_thread_.join();
        }

        // Restore original settings
        tcsetattr(fd_, TCSANOW, &old_tio_);
        ::close(fd_);
        fd_ = -1;
        is_open_ = false;
        return true;
    }

    bool isOpen() const { return is_open_; }

    bool configure(int dataBits = 8, char parity = 'N', int stopBits = 1)
    {
        if (!is_open_)
        {
            throw std::runtime_error("Serial port not open");
        }

        setDataBits(dataBits);
        setParity(parity);
        setStopBits(stopBits);
        return true;
    }

    size_t write(const std::string &data)
    {
        return write(reinterpret_cast<const uint8_t *>(data.c_str()),
                     data.size());
    }

    size_t write(const std::vector<uint8_t> &data)
    {
        return write(data.data(), data.size());
    }

    size_t write(const uint8_t *data, size_t size)
    {
        if (!is_open_)
        {
            throw std::runtime_error("Serial port not open");
        }

        ssize_t written = ::write(fd_, data, size);
        if (written == -1)
        {
            throw std::runtime_error("Failed to write to serial port");
        }
        return static_cast<size_t>(written);
    }

    size_t writePacket(uint8_t func_code, const std::vector<uint8_t> &payload)
    {
        const auto &header =
            send_frame_header_.empty() ? frame_header_ : send_frame_header_;
        const auto &tail =
            send_frame_tail_.empty() ? frame_tail_ : send_frame_tail_;

        if (header.empty() || tail.empty())
        {
            throw std::runtime_error("Frame format not set for sending");
        }

        std::vector<uint8_t> packet;
        packet.reserve(header.size() + 1 + payload.size() + tail.size());

        // Add header
        packet.insert(packet.end(), header.begin(), header.end());

        // Add function code
        packet.push_back(func_code);

        // Add payload
        packet.insert(packet.end(), payload.begin(), payload.end());

        // Add tail
        packet.insert(packet.end(), tail.begin(), tail.end());

        return write(packet);
    }

    size_t writePacket(uint8_t func_code, const std::string &payload)
    {
        return writePacket(
            func_code, std::vector<uint8_t>(payload.begin(), payload.end()));
    }

    size_t writePacket(uint8_t func_code, const uint8_t *payload, size_t size)
    {
        return writePacket(func_code,
                           std::vector<uint8_t>(payload, payload + size));
    }

  private:
    int fd_;
    bool is_open_;
    int speed_;
    std::string device_;
    struct termios old_tio_;
    std::thread read_thread_;
    std::atomic<bool> running_;
    std::function<void(const std::vector<uint8_t> &)> callback_;
    std::function<std::vector<uint8_t>(const std::vector<uint8_t> &)>
        protocol_parser_;
    std::vector<uint8_t> frame_header_;
    std::vector<uint8_t> frame_tail_;
    size_t frame_min_payload_size_ = 0;
    size_t function_code_offset_ = 0;
    std::vector<uint8_t> frame_buffer_;
    std::vector<uint8_t> send_frame_header_;
    std::vector<uint8_t> send_frame_tail_;
    std::map<uint8_t, std::function<void(const std::vector<uint8_t> &)>>
        function_handlers_;

    void readLoop()
    {
        std::vector<uint8_t> temp_buffer(1024);
        while (running_)
        {
            try
            {
                size_t bytesRead = read(temp_buffer.data(), temp_buffer.size());
                if (bytesRead > 0)
                {
                    std::vector<uint8_t> data(temp_buffer.begin(),
                                              temp_buffer.begin() + bytesRead);
                    if (!frame_header_.empty() && !frame_tail_.empty())
                    {
                        frame_buffer_.insert(frame_buffer_.end(), data.begin(),
                                             data.end());
                        processFrameBuffer();
                    }
                    else if (protocol_parser_)
                    {
                        std::vector<uint8_t> parsed = protocol_parser_(data);
                        if (!parsed.empty() && callback_)
                        {
                            callback_(parsed);
                        }
                    }
                    else if (callback_)
                    {
                        callback_(data);
                    }
                }
            }
            catch (const std::exception &e)
            {
                // Error handling
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }
    }

    void processFrameBuffer()
    {
        std::vector<uint8_t> packet;
        while (extractFrame(frame_buffer_, packet))
        {
            if (!function_handlers_.empty() &&
                packet.size() > function_code_offset_)
            {
                uint8_t func_code = packet[function_code_offset_];
                auto it = function_handlers_.find(func_code);
                if (it != function_handlers_.end())
                {
                    it->second(packet);
                    continue;
                }
            }

            if (callback_)
            {
                callback_(packet);
            }
        }
    }

    bool extractFrame(std::vector<uint8_t> &buffer,
                      std::vector<uint8_t> &packet)
    {
        if (frame_header_.empty() || frame_tail_.empty() ||
            buffer.size() < frame_header_.size() + frame_tail_.size() +
                                frame_min_payload_size_)
        {
            return false;
        }

        auto matchPattern = [&](const std::vector<uint8_t> &pattern,
                                size_t index) -> bool
        {
            if (index + pattern.size() > buffer.size())
            {
                return false;
            }
            for (size_t i = 0; i < pattern.size(); ++i)
            {
                if (buffer[index + i] != pattern[i])
                {
                    return false;
                }
            }
            return true;
        };

        size_t pos = 0;
        while (pos + frame_header_.size() <= buffer.size())
        {
            if (matchPattern(frame_header_, pos))
            {
                break;
            }
            pos++;
        }

        if (pos + frame_header_.size() > buffer.size())
        {
            if (buffer.size() > frame_header_.size())
            {
                buffer.erase(buffer.begin(),
                             buffer.begin() +
                                 (buffer.size() - frame_header_.size() + 1));
            }
            return false;
        }

        if (pos > 0)
        {
            buffer.erase(buffer.begin(), buffer.begin() + pos);
        }

        if (buffer.size() <
            frame_header_.size() + frame_tail_.size() + frame_min_payload_size_)
        {
            return false;
        }

        size_t search = frame_header_.size();
        while (search + frame_tail_.size() <= buffer.size())
        {
            if (matchPattern(frame_tail_, search))
            {
                packet.assign(buffer.begin() + frame_header_.size(),
                              buffer.begin() + search);
                buffer.erase(buffer.begin(),
                             buffer.begin() + search + frame_tail_.size());
                return true;
            }
            search++;
        }

        return false;
    }

    std::string read()
    {
        std::vector<uint8_t> buffer(1024);
        size_t bytesRead = read(buffer.data(), buffer.size());
        buffer.resize(bytesRead);
        return std::string(buffer.begin(), buffer.end());
    }

    size_t read(uint8_t *buffer, size_t maxSize)
    {
        if (!is_open_)
        {
            throw std::runtime_error("Serial port not open");
        }

        ssize_t bytesRead = ::read(fd_, buffer, maxSize);
        if (bytesRead == -1)
        {
            throw std::runtime_error("Failed to read from serial port");
        }
        return static_cast<size_t>(bytesRead);
    }

    void configureTermios()
    {
        struct termios tio;
        memset(&tio, 0, sizeof(tio));

        tio.c_iflag = 0; // Input flags
        tio.c_oflag = 0; // Output flags
        tio.c_cflag =
            CS8 | CREAD | CLOCAL; // 8 data bits, enable receiver, ignore modem
        tio.c_lflag = 0;          // Local flags

        // Set timeouts
        tio.c_cc[VMIN] = 0;   // Non-blocking read
        tio.c_cc[VTIME] = 10; // 1 second timeout

        if (tcsetattr(fd_, TCSANOW, &tio) != 0)
        {
            throw std::runtime_error("Failed to set terminal attributes");
        }
    }

    void setBaudRate(int baudrate)
    {
        speed_t speed;
        switch (baudrate)
        {
        case 9600:
            speed = B9600;
            break;
        case 19200:
            speed = B19200;
            break;
        case 38400:
            speed = B38400;
            break;
        case 57600:
            speed = B57600;
            break;
        case 115200:
            speed = B115200;
            break;
        default:
            throw std::invalid_argument("Unsupported baud rate");
        }

        struct termios tio;
        tcgetattr(fd_, &tio);
        cfsetispeed(&tio, speed);
        cfsetospeed(&tio, speed);
        if (tcsetattr(fd_, TCSANOW, &tio) != 0)
        {
            throw std::runtime_error("Failed to set baud rate");
        }
    }

    void setDataBits(int bits)
    {
        struct termios tio;
        tcgetattr(fd_, &tio);

        tio.c_cflag &= ~CSIZE;
        switch (bits)
        {
        case 5:
            tio.c_cflag |= CS5;
            break;
        case 6:
            tio.c_cflag |= CS6;
            break;
        case 7:
            tio.c_cflag |= CS7;
            break;
        case 8:
            tio.c_cflag |= CS8;
            break;
        default:
            throw std::invalid_argument("Invalid data bits");
        }

        tcsetattr(fd_, TCSANOW, &tio);
    }

    void setParity(char parity)
    {
        struct termios tio;
        tcgetattr(fd_, &tio);

        tio.c_cflag &= ~(PARENB | PARODD);
        if (parity == 'E')
        {
            tio.c_cflag |= PARENB; // Even parity
        }
        else if (parity == 'O')
        {
            tio.c_cflag |= (PARENB | PARODD); // Odd parity
        }
        // 'N' means no parity (default)

        tcsetattr(fd_, TCSANOW, &tio);
    }

    void setStopBits(int bits)
    {
        struct termios tio;
        tcgetattr(fd_, &tio);

        if (bits == 1)
        {
            tio.c_cflag &= ~CSTOPB; // 1 stop bit
        }
        else if (bits == 2)
        {
            tio.c_cflag |= CSTOPB; // 2 stop bits
        }
        else
        {
            throw std::invalid_argument("Invalid stop bits");
        }

        tcsetattr(fd_, TCSANOW, &tio);
    }
};