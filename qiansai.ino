#include <WiFi.h>

// ================= 1. 可配置区域 =================

// WiFi
const char* WIFI_SSID     = "eason";
const char* WIFI_PASSWORD = "11111111";

// 巴法云 TCP
const char* BEMFA_HOST = "bemfa.com";
const int   BEMFA_PORT = 8344;
const char* BEMFA_UID  = "39d32b4c415aa704cbb9093804ecef02";
const char* BEMFA_TOPIC = "data";

// 串口
#define GPS_SERIAL Serial1 // UART1
#define HR_SERIAL Serial // UART0

#define GPS_RX 16
#define GPS_TX 17

// 串口
#define GPS_SERIAL Serial1 // 串口1 → GPS
#define HR_SERIAL Serial // 串口0 → 心率 + 调试

// ================= 数据 =================
float latitude = 30.0;
float longitude = 120.0;

int heartRate = 0;
int spo2 = 0;

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL = 5000;

WiFiClient client;

// ================= 工具函数 =================
float convertToDecimal(float raw)
{
int degrees = (int)(raw / 100);
float minutes = raw - degrees * 100;
return degrees + minutes / 60.0;
}

// ================= GPS解析 =================
void parseGPS()
{
static String line = "";

while (GPS_SERIAL.available())
{
    char c = GPS_SERIAL.read();

    if (c == '\n')
    {
        if (line.startsWith("$GNGGA") || line.startsWith("$GPGGA"))
        {
            int idx[15], count = 0;

            for (int i = 0; i < line.length(); i++)
                if (line[i] == ',') idx[count++] = i;

            if (count > 5)
            {
                String latStr = line.substring(idx[1] + 1, idx[2]);
                String latDir = line.substring(idx[2] + 1, idx[3]);
                String lonStr = line.substring(idx[3] + 1, idx[4]);
                String lonDir = line.substring(idx[4] + 1, idx[5]);

                float lat = convertToDecimal(latStr.toFloat());
                float lon = convertToDecimal(lonStr.toFloat());

                if (latDir == "S") lat = -lat;
                if (lonDir == "W") lon = -lon;

                latitude  = lat;
                longitude = lon;
            }
        }
        line = "";
    }
    else
    {
        line += c;
    }
}

}

// ================= 心率解析 =================
void parseHR()
{
static String buffer = "";

while (HR_SERIAL.available())
{
    char c = HR_SERIAL.read();

    // ⚠️ 不要逐字打印（会干扰）
    if (c < 32 || c > 126) continue;

    buffer += c;

    int start = buffer.indexOf("FFR");
    int oPos  = buffer.indexOf("O", start);
    int yPos  = buffer.indexOf("Y", oPos);

    if (start != -1 && oPos != -1 && yPos != -1)
    {
        heartRate = buffer.substring(start + 3, oPos).toInt();
        spo2      = buffer.substring(oPos + 1, yPos).toInt();

        Serial.println("\n解析成功:");
        Serial.println("HR=" + String(heartRate));
        Serial.println("SPO2=" + String(spo2));

        buffer = "";
    }

    if (buffer.length() > 50) buffer = "";
}

}

// ================= 巴法云 =================
void sendToBemfa()
{
if (!client.connected())
{
if (!client.connect(BEMFA_HOST, BEMFA_PORT))
{
Serial.println("连接失败");
return;
}

    String loginCmd = "cmd=1&uid=" + String(BEMFA_UID) +
                      "&topic=" + String(BEMFA_TOPIC) + "\r\n";
    client.print(loginCmd);
    delay(200);
}

String data = "<" + String(heartRate) + "#" + String(spo2) + "#" +
              String(longitude, 6) + "#" + String(latitude, 6) + ">";

String sendCmd = "cmd=2&uid=" + String(BEMFA_UID) +
                 "&topic=" + String(BEMFA_TOPIC) +
                 "&msg=" + data + "\r\n";

client.print(sendCmd);

Serial.println("发送: " + data);

}

// ================= 初始化 =================
void setup()
{
Serial.begin(115200); // 串口0（心率+调试）

GPS_SERIAL.begin(115200, SERIAL_8N1, 17, 18); // 串口1 → GPS

WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

Serial.print("连接WiFi");
while (WiFi.status() != WL_CONNECTED)
{
    delay(500);
    Serial.print(".");
}

Serial.println("\nWiFi连接成功");

}

// ================= 主循环 =================
void loop()
{
parseGPS();
parseHR();

if (millis() - lastSendTime > SEND_INTERVAL)
{
    lastSendTime = millis();
    sendToBemfa();
}

}