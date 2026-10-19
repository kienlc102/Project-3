"""
Synthetic Dataset Generator and Augmentation Pipeline for Parking Diorama
Hỗ trợ tạo ảnh tổng hợp mô phỏng sa bàn (có xe vs không có xe)
và tiền xử lý ảnh thực tế chụp từ ESP32-CAM.
"""

import os
import math
import numpy as np


def generate_synthetic_sample(is_car=True, img_size=(64, 64)):
    """
    Tạo ra một mẫu ảnh xám 64x64 mô phỏng góc nhìn sa bàn từ ESP32-CAM:
    - Xe đồ chơi: Khối chữ nhật đối xứng, có mui xe, bánh xe 4 góc, đèn xe.
    - Không có xe: Giữ nguyên nền và vạch kẻ ô đỗ.
    """
    # Mặt sàn bãi đỗ (nền tối xám)
    img = np.full(img_size, 38.0, dtype=np.float32)
    
    # Nhiễu nhám mặt sàn
    noise = np.random.normal(0, 4.0, img_size).astype(np.float32)
    img = np.clip(img + noise, 0, 255)
    
    # Vạch kẻ ô đỗ xe (màu sáng)
    img[:, 4:6] += 70.0
    img[:, 58:60] += 70.0

    center_x = 32 + np.random.randint(-5, 6)
    center_y = 32 + np.random.randint(-5, 6)
    
    y_coords, x_coords = np.ogrid[:img_size[0], :img_size[1]]

    if is_car:
        # Góc đỗ xe chênh lệch nhẹ
        angle = np.random.uniform(-0.30, 0.30)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        # Tọa độ xoay
        xr = (x_coords - center_x) * cos_a + (y_coords - center_y) * sin_a
        yr = -(x_coords - center_x) * sin_a + (y_coords - center_y) * cos_a
        
        # Thân xe chính (~36x18 pixel)
        car_body_mask = (np.abs(xr) < 9) & (np.abs(yr) < 18)
        img[car_body_mask] = np.random.uniform(170, 215)
        
        # Kính chắn gió & mui xe
        roof_mask = (np.abs(xr) < 6) & (np.abs(yr) < 8)
        img[roof_mask] = np.random.uniform(80, 115)
        
        # 4 Bánh xe màu đen ở 4 góc
        for wx in [-9, 9]:
            for wy in [-12, 12]:
                wheel_mask = (np.abs(xr - wx) <= 2) & (np.abs(yr - wy) <= 3)
                img[wheel_mask] = 15.0
                
        # Đèn trước
        headlight_mask = (np.abs(xr) < 7) & (yr > 15) & (yr < 18)
        img[headlight_mask] = 245.0
        

    # Gradient ánh sáng phòng / đèn bàn
    illumination = np.linspace(0.9, 1.1, img_size[0])[:, None]
    img = np.clip(img * illumination, 0, 255).astype(np.uint8)
    
    return img


def create_synthetic_dataset(num_samples=1600):
    """
    Sinh ảnh tổng hợp 50:50 giữa Có xe (1.0) và Không có xe (0.0).
    Chỉ dùng kiểm tra pipeline, không dùng báo cáo độ chính xác thực tế.
    """
    X = []
    y = []
    
    half = num_samples // 2
    for _ in range(half):
        X.append(generate_synthetic_sample(is_car=True))
        y.append(1.0)
        
    for _ in range(half):
        X.append(generate_synthetic_sample(is_car=False))
        y.append(0.0)
        
    X = np.array(X, dtype=np.uint8)[..., np.newaxis]
    y = np.array(y, dtype=np.float32)
    
    indices = np.arange(len(X))
    np.random.seed(42)
    np.random.shuffle(indices)
    
    return X[indices], y[indices]
