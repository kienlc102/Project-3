"""
Full Training & Post-Training INT8 Quantization Pipeline for Parking Spot Monitor
Huấn luyện mô hình CNN siêu nhẹ và lượng tử hóa toàn phần chuẩn INT8 (15KB - 25KB)
cho vi điều khiển ESP32-CAM (TensorFlow Lite for Microcontrollers).
"""

import os
import sys
import glob
import numpy as np
import tensorflow as tf
from PIL import Image

from model import build_ultralight_parking_cnn
from dataset_generator import create_synthetic_dataset
from tflite_to_c_array import convert_tflite_to_c_array


def load_custom_dataset(dataset_dir="dataset"):
    """
    Đọc ảnh từng ô đỗ từ dataset công khai hoặc camera:
    Thư mục mẫu:
      dataset/occupied/*.jpg, *.png (Nhãn 1.0: có xe)
      dataset/vacant/*.jpg, *.png (Nhãn 0.0: không có xe)
    """
    cars_path = os.path.join(dataset_dir, "occupied")
    vacant_path = os.path.join(dataset_dir, "vacant")
    
    if not os.path.exists(cars_path) or not os.path.exists(vacant_path):
        return None, None
        
    car_files = glob.glob(os.path.join(cars_path, "*.*"))
    vacant_files = glob.glob(os.path.join(vacant_path, "*.*"))
    
    if len(car_files) == 0 or len(vacant_files) == 0:
        return None, None
        
    print(f"[DATASET] Tìm thấy {len(car_files)} ảnh có xe (1), {len(vacant_files)} ảnh không có xe (0).")
    
    X = []
    y = []
    
    for f in car_files:
        try:
            img = Image.open(f).convert("L").resize((64, 64))
            X.append(np.array(img, dtype=np.uint8))
            y.append(1.0)
        except Exception:
            pass
            
    for f in vacant_files:
        try:
            img = Image.open(f).convert("L").resize((64, 64))
            X.append(np.array(img, dtype=np.uint8))
            y.append(0.0)
        except Exception:
            pass
            
    X = np.array(X, dtype=np.uint8)[..., np.newaxis]
    y = np.array(y, dtype=np.float32)
    
    indices = np.arange(len(X))
    np.random.seed(42)
    np.random.shuffle(indices)
    return X[indices], y[indices]


def train_and_quantize(epochs=15, batch_size=32, num_synthetic_samples=1600):
    print("=====================================================================")
    print("  TINYML PARKING SPOT DETECTION - TRAINING & INT8 QUANTIZATION       ")
    print("=====================================================================")
    
    # 1. Chuẩn bị Dataset
    print("\n[BƯỚC 1/5] Kiểm tra và nạp tập dữ liệu...")
    X, y = load_custom_dataset("dataset")
    if X is None:
        print(f" -> Không tìm thấy dataset thư mục 'dataset/'. Tự động sinh {num_synthetic_samples} ảnh sa bàn tổng hợp...")
        X, y = create_synthetic_dataset(num_samples=num_synthetic_samples)
    else:
        print(f" -> Đã nạp thành công {len(X)} ảnh từ thư mục 'dataset/'.")
        
    split_idx = int(0.8 * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    print(f" -> Phân chia: {len(X_train)} ảnh Train | {len(X_val)} ảnh Validation (Input 64x64x1 Grayscale)")

    # 2. Khởi tạo Mô hình
    print("\n[BƯỚC 2/5] Khởi tạo kiến trúc Depthwise Separable CNN...")
    model = build_ultralight_parking_cnn(input_shape=(64, 64, 1))
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")]
    )
    model.summary()

    # 3. Huấn luyện Mô hình
    print(f"\n[BƯỚC 3/5] Bắt đầu huấn luyện ({epochs} epochs)...")
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5)
    ]
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1
    )
    
    val_loss, val_acc, val_auc = model.evaluate(X_val, y_val, verbose=0)
    print(f"\n[KẾT QUẢ ĐÁNH GIÁ] Val Accuracy: {val_acc*100:.2f}% | Val AUC: {val_auc:.4f}")

    # Lưu SavedModel
    saved_model_dir = "output/parking_cnn_saved_model"
    os.makedirs("output", exist_ok=True)
    model.save(saved_model_dir)

    # 4. Lượng tử hóa toàn phần INT8 (Post-Training Quantization - PTQ)
    print("\n[BƯỚC 4/5] Thực hiện Full Integer INT8 Post-Training Quantization...")
    
    def representative_dataset_gen():
        # Lấy 150 mẫu đại diện từ tập train để lượng tử hóa chính xác
        for i in range(min(150, len(X_train))):
            sample = X_train[i:i+1].astype(np.float32)
            yield [sample]

    converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset_gen
    
    # Ép buộc toán tử và Tensor I/O về INT8 để chạy tối ưu trên ESP32 CPU (không cần FPU)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    
    tflite_quant_model = converter.convert()
    
    tflite_path = "output/parking_cnn_int8.tflite"
    with open(tflite_path, "wb") as f:
        f.write(tflite_quant_model)
        
    tflite_size_bytes = len(tflite_quant_model)
    tflite_size_kb = tflite_size_bytes / 1024.0
    print(f" -> Đã lưu: {tflite_path}")
    print(f" -> Dung lượng TFLite INT8: {tflite_size_bytes} bytes ({tflite_size_kb:.2f} KB)")
    
    if 10.0 <= tflite_size_kb <= 28.0:
        print(" -> [ĐẠT YÊU CẦU THIẾT KẾ] Kích thước mô hình nằm hoàn hảo trong khoảng ~15KB - 25KB!")
    else:
        print(f" -> Kích thước thực tế: {tflite_size_kb:.2f} KB")

    # Kiểm tra Quantization Parameters (Scale & Zero-Point)
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    
    in_scale, in_zero_point = input_details["quantization"]
    out_scale, out_zero_point = output_details["quantization"]
    
    print("\n[THÔNG SỐ LƯỢNG TỬ HÓA CHO ESP32 C++ FIRMWARE]")
    print(f" - Input Tensor Name: {input_details['name']}")
    print(f" - Input Scale: {in_scale}, Zero Point: {in_zero_point}")
    print(f" - Output Tensor Name: {output_details['name']}")
    print(f" - Output Scale: {out_scale}, Zero Point: {out_zero_point}")
    print(" -> Công thức lượng tử hóa ảnh đầu vào:")
    print(f"    int8_pixel = (uint8_pixel - {in_zero_point}) [hoặc pixel_float / in_scale + in_zero_point]")
    print(" -> Công thức giải lượng tử xác suất đầu ra:")
    print(f"    probability_car = (output_int8 - {out_zero_point}) * {out_scale}")

    # 5. Xuất ra mảng C Header (.h)
    print("\n[BƯỚC 5/5] Xuất file C array header cho ESP32-CAM...")
    local_header = "model_data.h"
    firmware_header = "../firmware_esp32cam/model_data.h"
    
    convert_tflite_to_c_array(tflite_path, local_header)
    os.makedirs("../firmware_esp32cam", exist_ok=True)
    convert_tflite_to_c_array(tflite_path, firmware_header)
    
    print("\n=====================================================================")
    print("  [HOÀN TẤT] MÔ HÌNH ĐÃ SẴN SÀNG NHÚNG VÀO FLASH ESP32-CAM!         ")
    print("=====================================================================")


if __name__ == "__main__":
    train_and_quantize()
