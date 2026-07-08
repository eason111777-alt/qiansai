import serial
import time


servo_angle=0
turningflag=11

count = 0

# 1. 配置并打开串口
try:
    ser4 = serial.Serial(
        port='/dev/ttyS2',  # 请根据实际情况修改端口号
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05  # 设置短超时，避免 read 阻塞死循环
    )
    ser5 = serial.Serial(
        port='/dev/ttyS3',  # 请根据实际情况修改端口号
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05  # 设置短超时，避免 read 阻塞死循环
    )    
    print(f"成功打开串口 {ser4.name}")
except Exception as e:
    print(f"串口打开失败: {e}")
    exit()

# 建立动态接收缓冲区 (替代 C 语言中的定长 rxbuf[60])
rx_buffer = bytearray()
ser5_buf = bytearray()


def parse_ser5_packet(buf):
    """
    从缓冲区中解析 "A<angle>F<turningflag>L" 格式的数据包。
    格式示例: A90.5F11L 或 A-85F13L

    返回: (angle, flag) 解析成功（如果是粘包，返回最后一组最新数据）
           None         数据不完整或全错，等待更多字节
    """
    # 将字节数组解码为字符串
    data = buf.decode('utf-8', 'ignore')
    
    latest_angle = None
    latest_flag = None
    
    # 设定一个查找起点
    search_idx = 0
    
    # 持续在字符串中寻找 A...F...L
    while True:
        # 1. 找 'A' 的位置
        a_idx = data.find('A', search_idx)
        if a_idx == -1:
            break  # 没找到 A，结束查找
            
        # 2. 从 'A' 后面找 'F' 的位置
        f_idx = data.find('F', a_idx + 1)
        if f_idx == -1:
            break  # 找到了 A 但还没收到 F，等下次接收
            
        # 3. 从 'F' 后面找 'L' 的位置
        l_idx = data.find('L', f_idx + 1)
        if l_idx == -1:
            break  # 找到了 F 但还没收到结尾 L，等下次接收
            
        # 4. A, F, L 都齐了，截取中间的字符串并转换
        try:
            angle_str = data[a_idx + 1 : f_idx]  # A 和 F 中间的部分
            flag_str = data[f_idx + 1 : l_idx]   # F 和 L 中间的部分
            
            angle = float(angle_str)
            flag = int(flag_str)
            
            # 记录下这组成功解析的值
            latest_angle = angle
            latest_flag = flag
            
        except ValueError:
            # 如果截取出来的不是数字（比如发生错位乱码），直接忽略本次提取
            pass
            
        # 5. 滑动查找起点到 'L' 后面，继续看有没有下一帧（处理粘包）
        search_idx = l_idx + 1
        
    # 循环结束后，如果提取到了有效数据，就返回最后一次的值
    if latest_angle is not None and latest_flag is not None:
        return latest_angle, latest_flag
    else:
        return None


# 相当于 C 语言中的 while(1)
while True:
    try:
        # 2. 读取 ser5 数据并解析 A<angle>F<flag> 包
        if ser5.in_waiting > 0:
            ser5_buf.extend(ser5.read(ser5.in_waiting))
            result = parse_ser5_packet(ser5_buf)
            if result is not None:
                servo_angle, turningflag = result
                ser5_buf.clear()
                print(f"收到 ser5 -> servo_angle: {servo_angle}, turningflag: {turningflag}")

        # 3. 读取 ser4 数据
        if ser4.in_waiting > 0:
            data = ser4.read(ser4.in_waiting)
            rx_buffer.extend(data)
        else:
            # 没数据时短暂休眠，避免 while 循环占满 100% CPU
            time.sleep(0.01)
            continue

        # 3. 寻找包头并解析 (替代 C 代码中 for 循环找 4 个 255 的逻辑)
        # 连续 4 个 0xFF 构成的帧头
        frame_header = b'\xff\xff\xff\xff'

        # 只要缓冲区里还有帧头，就持续解析
        while frame_header in rx_buffer:
            # 找到帧头的起始索引
            header_index = rx_buffer.find(frame_header)

            # C 代码解析逻辑对照：
            # C 中 j 是第 4 个 255 的索引，即 j = header_index + 3
            # index_1 = j + 17 = header_index + 20
            # 取值最远用到 index_1 + 5 = header_index + 25
            # 因此，从帧头开始，至少需要 26 个字节才算完整的一帧
            if len(rx_buffer) >= header_index + 26:
                index_1 = header_index + 20

                # === 3. 解析 Distance ===
                # 原逻辑等效于：高字节左移 8 位 + 低字节
                dist_high = rx_buffer[index_1 + 2]
                dist_low  = rx_buffer[index_1 + 3]
                distance = (dist_high << 8) | dist_low

                # === 4. 解析 Azimuth ===
                # 原逻辑等效于：- 字节4 + 字节5
                azi_high = rx_buffer[index_1 + 4]
                azi_low  = rx_buffer[index_1 + 5]
                azimuth = -azi_high + azi_low

                count+=1
        
                if count == 5:
                    count = 0
                    print(f"成功解析一帧 -> Distance: {distance}, Azimuth: {azimuth},Servo:{servo_angle}")
                    
                    

                    
                    send_string = f"FFD{distance}A{azimuth}T{servo_angle}F{turningflag}L"


                    ser5.write(send_string.encode('utf-8'))
                    ser5_buf.clear()
                     
                

                # 4. 滑动窗口：将已经处理过的数据（包含当前完整帧）从缓冲区中移除
                rx_buffer = rx_buffer[header_index + 26:]
            else:
                # 找到了帧头，但后续的数据还没通过串口接收完整
                # 跳出内部处理循环，等待下一次 while True 读取更多字节
                break

    except KeyboardInterrupt:
        print("\n程序被手动中断 (Ctrl+C)")
        break
    except Exception as e:
        print(f"发生未知错误: {e}")
        break

# 5. 安全释放资源   
if 'ser4' in locals() and ser4.is_open:
    ser4.close()
    print("串口已安全关闭")
