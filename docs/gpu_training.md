# Train trên NVIDIA RTX 3050 Ti bằng TensorFlow và WSL2

Máy đã nhận RTX 3050 Ti 4 GB qua `nvidia-smi`. Môi trường `.venv` Windows dùng Python 3.12 / TensorFlow 2.20 nhưng không nhận CUDA GPU. TensorFlow chỉ hỗ trợ CUDA trên Windows native đến 2.10; pipeline hiện dùng Keras mới nên dùng **Ubuntu trên WSL2** để train GPU.

Tham khảo chính thức: [cài TensorFlow](https://www.tensorflow.org/install/pip), [memory growth](https://www.tensorflow.org/api_docs/python/tf/config/experimental/set_memory_growth).

## 1. Cài Ubuntu cho WSL2

Máy hiện có distro `docker-desktop` ở WSL2; cần một distro Ubuntu riêng cho môi trường Python. Chạy trong PowerShell, dùng quyền Administrator nếu Windows yêu cầu:

```powershell
wsl --install -d Ubuntu-24.04
```

Hoàn tất thiết lập username/password Linux và khởi động lại máy nếu trình cài yêu cầu. Kiểm tra:

```powershell
wsl --list --verbose
```

Ubuntu cần ở VERSION 2. Nếu đang VERSION 1, chạy `wsl --set-version Ubuntu-24.04 2` (thay tên distro theo danh sách thực tế). Dùng Ubuntu 24.04 để có Python 3.12 phù hợp với phiên bản TensorFlow của project.

## 2. Tạo môi trường Python bên trong Ubuntu

Mở Ubuntu:

```powershell
wsl -d Ubuntu-24.04
```

Các lệnh từ đây chạy trong **terminal Ubuntu**, không phải PowerShell:

```bash
nvidia-smi
sudo apt update
sudo apt install -y python3-venv python3-pip
cd /mnt/d/Project-3
python3 -m venv ~/.venvs/parking-gpu
source ~/.venvs/parking-gpu/bin/activate
python -m pip install --upgrade pip
python -m pip install -r ai_model/requirements-gpu.txt
```

Môi trường Linux được tạo riêng trong `~/.venvs/parking-gpu`. Không dùng `.venv/Scripts/python.exe` của Windows để chạy GPU. Gói `tensorflow[and-cuda]` cài các thư viện CUDA user-space tương ứng; không cần cài CUDA Toolkit Windows theo con số `CUDA Version` trên `nvidia-smi`.

Nếu `nvidia-smi` không chạy được trong Ubuntu, kiểm tra WSL/driver trước khi train. Đừng cài driver NVIDIA Linux thay cho driver Windows trong WSL.

## 3. Kiểm tra TensorFlow thực sự dùng GPU

```bash
cd /mnt/d/Project-3
source ~/.venvs/parking-gpu/bin/activate
python ai_model/train_and_quantize.py --device gpu --check-device
```

Lệnh phải in tên GPU, `memory growth enabled` và kết quả phép nhân ma trận chạy trên `GPU:0`. Nếu GPU không nhận, lệnh dừng với thông báo lỗi trước khi đọc dataset hoặc tạo output, không âm thầm train CPU.

## 4. Train trên GPU

Dataset đã chia tại `ai_model/dataset`, không cần chia lại:

```bash
python ai_model/check_dataset.py --dataset-dir ai_model/dataset
python ai_model/train_and_quantize.py --dataset-dir ai_model/dataset --output-dir ai_model/output/run_gpu01 --epochs 40 --batch-size 32 --device gpu
```

Chỉ tiếp tục train sau khi kiểm tra dữ liệu thành công. Nếu thư mục `run_gpu01` đã có nội dung, dùng tên mới. Nếu gặp `ResourceExhaustedError` do VRAM, giảm batch xuống 16 hoặc 8 và dùng thư mục output mới.

Cấu hình train:

- Tự nhận GPU đầu tiên; `--device gpu` yêu cầu có GPU.
- Memory growth cấp VRAM theo nhu cầu, không đặt trước toàn bộ VRAM. Cấu hình này không bảo đảm tránh mọi lỗi thiếu bộ nhớ.
- Giữ float32 để đơn giản hóa pipeline lưu model và chuyển INT8; chưa bật mixed precision.
- Dữ liệu được shuffle/batch/prefetch bằng `tf.data` để chuẩn bị batch tiếp theo trong lúc model xử lý batch hiện tại.
- Không ép mọi toán tử lên GPU: đọc ảnh, một số thao tác phụ và chuyển INT8 có thể chạy CPU. Log GPU ở đầu xác nhận thiết bị được cấu hình; `--check-device` kiểm tra placement bằng một phép tính thật.
- Tên thiết bị và cấu hình được ghi trong `run_config.json`.

Mở terminal Ubuntu thứ hai và chạy `nvidia-smi -l 1` để quan sát. Mạng nhỏ có thể không giữ mức GPU utilization cao liên tục. Đường dẫn `/mnt/d` thuận tiện để dùng chung dữ liệu với Windows; truy cập nhiều file nhỏ có thể chậm hơn filesystem Linux.

## 5. Kiểm tra model sau train

Vẫn trong Ubuntu và môi trường `parking-gpu`:

```bash
python ai_model/evaluate_model.py --model-dir ai_model/output/run_gpu01 --data-dir ai_model/dataset/val --split val --threshold 0.5 --report-dir ai_model/output/run_gpu01/validation
threshold=$(python -c "import json; print(json.load(open('ai_model/output/run_gpu01/validation/metrics.json'))['recommended_int8_threshold_from_validation'])")
python ai_model/evaluate_model.py --model-dir ai_model/output/run_gpu01 --data-dir ai_model/dataset/test --split test --threshold "$threshold" --report-dir ai_model/output/run_gpu01/test
```

Chọn ngưỡng trên validation, giữ nguyên khi kiểm tra test. Cách đọc báo cáo ở [hướng dẫn train và đánh giá](training_and_evaluation.md).

Nếu chỉ cần chạy CPU trên Windows, vẫn dùng môi trường `.venv` và thêm `--device cpu`. Mặc định `--device auto` chọn GPU nếu TensorFlow nhận được, hoặc in thông báo chuyển sang CPU. GPU không thể được bật trên TensorFlow Windows hiện tại chỉ bằng sửa file Python.
