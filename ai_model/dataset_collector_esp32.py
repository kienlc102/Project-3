"""
ESP32-CAM Live Dataset Collector for Diorama Setup
Công cụ hỗ trợ thu thập ảnh trực tiếp từ ESP32-CAM qua WiFi
để huấn luyện mô hình phân loại ô đỗ có xe (1) / không có xe (0).
"""

import os
import time
import urllib.request
import argparse


def capture_stream_samples(esp32_cam_ip, label_name, count=50, delay_sec=0.8, output_dir="dataset"):
    """
    Tải ảnh từ endpoint chụp ảnh của ESP32-CAM (mặc định: http://<ip>/capture)
    và lưu vào thư mục dataset/<label_name>/.
    """
    save_folder = os.path.join(output_dir, label_name)
    os.makedirs(save_folder, exist_ok=True)
    
    capture_url = f"http://{esp32_cam_ip}/capture"
    print(f"[COLLECTOR] Bắt đầu thu thập {count} ảnh cho nhãn '{label_name}'...")
    print(f" -> URL: {capture_url}")
    print(f" -> Thư mục lưu: {save_folder}")
    print(" -> Nhấn Ctrl+C để dừng sớm nếu cần.\n")

    saved = 0
    for i in range(count):
        filename = f"{label_name}_{int(time.time())}_{i:03d}.jpg"
        filepath = os.path.join(save_folder, filename)
        
        try:
            req = urllib.request.Request(capture_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                image_data = response.read()
                with open(filepath, "wb") as f:
                    f.write(image_data)
                    
            saved += 1
            print(f"[{saved}/{count}] Đã lưu ảnh: {filename} ({len(image_data)} bytes)")
            time.sleep(delay_sec)
            
        except Exception as e:
            print(f"[CẢNH BÁO] Không thể chụp ảnh từ {capture_url}: {e}")
            time.sleep(2.0)
            
    print(f"\n[HOÀN TẤT] Đã thu thập thành công {saved} ảnh vào '{save_folder}'!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thu thập dataset từ ESP32-CAM cho Sa bàn")
    parser.add_argument("--ip", type=str, default="192.168.1.50", help="Địa chỉ IP của ESP32-CAM")
    parser.add_argument("--label", type=str, default="occupied", choices=["occupied", "vacant"], help="occupied = có xe (1), vacant = không có xe (0)")
    parser.add_argument("--count", type=int, default=100, help="Số lượng ảnh cần chụp")
    parser.add_argument("--interval", type=float, default=0.8, help="Thời gian chờ giữa các lần chụp (giây)")
    
    args = parser.parse_args()
    capture_stream_samples(args.ip, args.label, args.count, args.interval)
