"""
Ultra-Lightweight CNN Architecture for Edge Parking Spot Monitoring (TinyML)
Input: 64x64x1 (Grayscale image)
Architecture: Depthwise Separable Convolutions + Global Average Pooling
Output: 1 Neuron with Sigmoid activation (1: Occupied / Car present, 0: Vacant / No car)
Target footprint: < 25KB quantized INT8 for ESP32-CAM (TFLite Micro)
"""

import tensorflow as tf
from tensorflow.keras import layers, models


def build_ultralight_parking_cnn(input_shape=(64, 64, 1)):
    """
    Xây dựng kiến trúc CNN siêu nhẹ tối ưu hóa cho vi điều khiển ESP32-CAM.
    
    Đặc điểm thiết kế:
    - Input: 64x64x1 (ảnh xám, tiết kiệm 66% RAM so với RGB).
    - Chuẩn hóa đầu vào [0, 1] qua layer Rescaling.
    - Standard Conv2D khởi tạo trích xuất đặc trưng cơ bản ban đầu (16 filters).
    - 3 khối Depthwise Separable Convolution giúp giảm ~8-9 lần số lượng phép tính (MACs)
      so với Standard Convolution thông thường.
    - GlobalAveragePooling2D thay thế hoàn toàn Flatten + Dense nhiều nơ-ron,
      triệt tiêu nguy cơ quá khớp (overfitting) và giảm 90% số lượng trọng số kết nối.
    - Dropout 0.25 để tăng cường tính ổn định chống nhiễu ánh sáng.
    - Output: 1 nơ-ron Sigmoid (Có xe = 1, Không có xe = 0).
    """
    inputs = layers.Input(shape=input_shape, name="image_input")
    
    # 1. Chuẩn hóa pixel về khoảng [0.0, 1.0]
    x = layers.Rescaling(1.0 / 255.0, name="rescaling")(inputs)
    
    # 2. Khối Conv2D thông thường đầu tiên (Initial Feature Extractor)
    x = layers.Conv2D(16, (3, 3), strides=(1, 1), padding="same", use_bias=False, name="conv1")(x)
    x = layers.BatchNormalization(name="bn1")(x)
    x = layers.ReLU(max_value=6.0, name="relu1")(x)
    x = layers.MaxPooling2D(pool_size=(2, 2), name="pool1")(x)  # 64x64 -> 32x32

    # 3. Depthwise Separable Block 1 (32 filters)
    x = layers.DepthwiseConv2D((3, 3), padding="same", use_bias=False, name="dw_conv2")(x)
    x = layers.BatchNormalization(name="dw_bn2")(x)
    x = layers.ReLU(max_value=6.0, name="dw_relu2")(x)
    x = layers.Conv2D(32, (1, 1), padding="same", use_bias=False, name="pw_conv2")(x)
    x = layers.BatchNormalization(name="pw_bn2")(x)
    x = layers.ReLU(max_value=6.0, name="pw_relu2")(x)
    x = layers.MaxPooling2D(pool_size=(2, 2), name="pool2")(x)  # 32x32 -> 16x16

    # 4. Depthwise Separable Block 2 (48 filters)
    x = layers.DepthwiseConv2D((3, 3), padding="same", use_bias=False, name="dw_conv3")(x)
    x = layers.BatchNormalization(name="dw_bn3")(x)
    x = layers.ReLU(max_value=6.0, name="dw_relu3")(x)
    x = layers.Conv2D(48, (1, 1), padding="same", use_bias=False, name="pw_conv3")(x)
    x = layers.BatchNormalization(name="pw_bn3")(x)
    x = layers.ReLU(max_value=6.0, name="pw_relu3")(x)
    x = layers.MaxPooling2D(pool_size=(2, 2), name="pool3")(x)  # 16x16 -> 8x8

    # 5. Depthwise Separable Block 3 (64 filters)
    x = layers.DepthwiseConv2D((3, 3), padding="same", use_bias=False, name="dw_conv4")(x)
    x = layers.BatchNormalization(name="dw_bn4")(x)
    x = layers.ReLU(max_value=6.0, name="dw_relu4")(x)
    x = layers.Conv2D(64, (1, 1), padding="same", use_bias=False, name="pw_conv4")(x)
    x = layers.BatchNormalization(name="pw_bn4")(x)
    x = layers.ReLU(max_value=6.0, name="pw_relu4")(x)

    # 6. Global Average Pooling (8x8x64 -> 64)
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(0.25, name="dropout")(x)
    
    # 7. Sigmoid: điểm số có xe; nhãn occupied = 1, vacant = 0.
    outputs = layers.Dense(1, activation="sigmoid", name="car_probability")(x)
    
    model = models.Model(inputs=inputs, outputs=outputs, name="UltraLight_Parking_CNN")
    return model


if __name__ == "__main__":
    model = build_ultralight_parking_cnn()
    model.summary()
