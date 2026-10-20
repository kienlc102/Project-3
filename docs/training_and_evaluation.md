# Tự train và kiểm tra CNN giám sát ô đỗ

Mục tiêu: tự học trọng số cho CNN trong `ai_model/model.py`, không dùng pretrained model. Nhãn **1 = có xe**, **0 = không có xe**. Sau quy trình này bạn có model float `.keras`, model INT8 `.tflite`, header C và báo cáo trên tập test riêng.

Tất cả lệnh PowerShell dưới đây chạy từ **`D:\Project-3`**. Không cần `cd ai_model`.

**Nếu dùng RTX 3050 Ti để train GPU:** làm theo [hướng dẫn GPU/WSL2](gpu_training.md) để tạo môi trường Linux và chạy với `--device gpu`. Các lệnh PowerShell trong tài liệu này dùng môi trường Windows; TensorFlow 2.20 ở môi trường đó chỉ chạy CPU. Script mặc định `--device auto`, in thiết bị đã chọn trước khi train.

## 1. Chọn dữ liệu và xác định đơn vị một ảnh

Mỗi ảnh cần thể hiện **một ô đỗ**, không phải toàn bộ bãi xe. Để làm theo cách chia ngày tự động bên dưới, nên dùng bản **CNR-EXT** từ [CNRPark+EXT](https://cnrpark.it/): tải gói **CNR-EXT-Patches-150x150.zip**, giải nén và giữ cả `PATCHES` lẫn `LABELS`. Có thể dùng PKLot nhưng cần xử lý annotation riêng. Giữ thông tin camera, ngày chụp, ảnh nguồn.

- CNRPark: `busy` → `occupied` → 1; `free` → `vacant` → 0.
- Nếu dùng ảnh toàn cảnh, cắt từng ô đỗ theo annotation trước. Không center crop toàn cảnh rồi coi đó là một ô đỗ.
- Kiểm tra trực quan vài chục ảnh mỗi lớp để phát hiện gán nhãn ngược, ảnh hỏng hoặc crop mất xe.
- Có thể bắt đầu với khoảng 1.000–3.000 ảnh mỗi lớp nếu máy đủ RAM. Đây là mốc thực hành, không phải số lượng bảo đảm độ chính xác. Sự đa dạng quan trọng hơn nhiều ảnh gần trùng.
- Hai lớp nên có nhiều ngày, ánh sáng, góc nhìn; tránh để lớp có xe chỉ thuộc một camera còn lớp không có xe chỉ thuộc camera khác.

## 2. Tạo môi trường

```powershell
cd D:\Project-3
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ai_model\requirements.txt
.\.venv\Scripts\python.exe -X utf8 -c "import tensorflow as tf; import numpy; from PIL import Image; print('TensorFlow:', tf.__version__)"
```

Khi lệnh cuối in được phiên bản, môi trường đã import được các thư viện. Các lệnh dùng `-X utf8` để in tiếng Việt trên Windows. Chưa cần GPU để bắt đầu với tập nhỏ; thời gian train phụ thuộc CPU/GPU, số ảnh và batch size.

## 3. Chia dữ liệu trước khi train

Đầu vào train cần có cấu trúc sau:

```text
ai_model/dataset/
├── train/
│   ├── occupied/
│   └── vacant/
├── val/
│   ├── occupied/
│   └── vacant/
└── test/
    ├── occupied/
    └── vacant/
```

Mỗi thư mục lớp chứa ảnh JPG/PNG/BMP/WebP; có thể có thư mục con để giữ metadata. Tỷ lệ khởi đầu khoảng **70% train / 15% val / 15% test**, nhưng ưu tiên tách nhóm đúng hơn tỷ lệ tuyệt đối.

| Tập | Vai trò |
|---|---|
| Train | Cập nhật trọng số |
| Val | Chọn epoch tốt nhất, cấu hình và ngưỡng |
| Test | Đánh giá cuối cùng sau khi chốt mọi lựa chọn |

Không chia ngẫu nhiên từng frame liên tiếp. Các ảnh cùng một chuỗi chụp hoặc cùng lượt xe đỗ cần nằm cùng tập. Nếu một ảnh toàn cảnh sinh nhiều crop ô đỗ, giữ các crop từ ảnh nguồn đó trong cùng tập. Chọn ngày/camera riêng cho test để đánh giá tình huống muốn báo cáo.

### Chia tự động CNR-EXT theo ngày

Dataset hiện được giải nén tại `CNR-EXT-Patches-150x150/` ở thư mục gốc project, trong đó có `PATCHES/` và `LABELS/`. Liệt kê các file nhãn:

```powershell
Get-ChildItem CNR-EXT-Patches-150x150\LABELS
```

File `LABELS/all.txt` đã có toàn bộ danh sách ảnh và nhãn. Đường dẫn dạng `SUNNY/.../image.jpg 0` hoặc `... 1` tính từ thư mục `PATCHES`, nên chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\prepare_dataset.py --source CNR-EXT-Patches-150x150\PATCHES --labels CNR-EXT-Patches-150x150\LABELS\all.txt --destination ai_model\dataset --max-per-class-per-day 100
```

Nếu lưu dataset ở vị trí khác, thay các đường dẫn tương ứng. `--source` phải là gốc mà đường dẫn ảnh trong file nhãn tham chiếu tới. Script không tải dữ liệu qua mạng. Nếu đã chia dữ liệu và có `ai_model/dataset/split_manifest.json`, bỏ qua lệnh chuẩn bị này để tiếp tục kiểm tra dữ liệu ở bước 4.

Script gộp danh sách ảnh, lấy ngày từ đường dẫn, chia các ngày theo seed 42 rồi copy ảnh sang train/val/test. Tùy chọn `--max-per-class-per-day 100` lấy ngẫu nhiên tối đa 100 ảnh mỗi lớp mỗi ngày để tạo thí nghiệm đầu tiên nhẹ hơn; bỏ tùy chọn khi muốn dùng toàn bộ dữ liệu. Toàn bộ camera trong cùng ngày nằm cùng tập. Tỷ lệ ngày xấp xỉ 70/15/15; tỷ lệ số ảnh có thể khác. Đây là **cách chia mới của project**, không phải cách chia benchmark gốc. Cấu hình được lưu ở `dataset/split_manifest.json`.

Nếu dữ liệu đã nằm trong thư mục `free/busy` hoặc `vacant/occupied` và tên ảnh/đường dẫn có ngày chụp, có thể bỏ `--labels` để suy nhãn từ thư mục. Cần ít nhất ba ngày. CNRPark nhỏ chỉ có hai ngày nên không phù hợp cách chia ba tập theo ngày này; dùng CNR-EXT hoặc tự chia theo các lượt đỗ độc lập và ghi rõ phương pháp.

Thư mục đích phải trống; script không di chuyển hay xóa ảnh gốc. Nó copy các ảnh được chọn, nên cần dung lượng đĩa và RAM phù hợp. Nếu máy hạn chế, chọn trước một tập con đa dạng có ít nhất ba ngày và đủ hai lớp; không lấy toàn bộ ảnh của một ngày duy nhất.

Giữ thông tin ngày chụp và ảnh nguồn khi chia nhóm, tránh trộn và đổi tên tất cả dữ liệu trước bước này. Pipeline tự tiền xử lý ảnh bằng `dataset_io.py`, nên bạn có thể dùng trực tiếp ảnh gốc đã cắt theo ô đỗ. Mọi ảnh đều được grayscale, center crop hình vuông và bilinear resize về `64×64`, giữ pixel `0–255`; Rescaling nằm trong model.

## 4. Kiểm tra dữ liệu trước khi train

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\check_dataset.py --dataset-dir ai_model\dataset
```

Lệnh kiểm tra:

- Mỗi tập có ảnh ở cả hai lớp và ảnh đọc được.
- Đầu vào có shape `(N, 64, 64, 1)`, dtype `uint8`, pixel trong miền `0–255`.
- Không có ảnh sau tiền xử lý giống hệt nhau nhưng mang hai nhãn khác nhau trong cùng tập.
- Không có ảnh sau tiền xử lý giống hệt nhau xuất hiện ở nhiều tập.

Chỉ tiếp tục khi có dòng `PASS`. Kiểm tra hash chỉ phát hiện ảnh giống hệt, không thay thế việc chia nhóm: hai frame chỉ lệch vài pixel vẫn có thể gây rò rỉ dữ liệu.

## 5. Train CNN từ đầu

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\train_and_quantize.py --dataset-dir ai_model\dataset --output-dir ai_model\output\run01 --epochs 40 --batch-size 32
```

Script đọc train và val riêng; **không đọc test để học/chọn model**, không tự dùng ảnh tổng hợp khi thiếu dữ liệu. Nó đặt seed 42, dùng Adam `0.001`, binary cross-entropy, EarlyStopping và ReduceLROnPlateau. Checkpoint có `val_loss` thấp nhất được dùng để xuất model.

Một epoch là một lượt đi qua tập train. Trong log:

- `loss`/`accuracy`: kết quả trên train.
- `val_loss`/`val_accuracy`: kết quả trên val.
- Train tốt dần và val tốt dần: tín hiệu tích cực.
- Train tiếp tục tốt nhưng `val_loss` tăng: có thể overfit; checkpoint giữ epoch tốt hơn.
- Cả train và val gần đoán ngẫu nhiên trên tập cân bằng: kiểm tra nhãn, ảnh, crop, phân bố dữ liệu trước khi tăng kiến trúc.

`accuracy` trong log dùng ngưỡng mặc định 0.5, không phải ngưỡng 0.75 trong firmware.

Nếu thiếu RAM, giảm `--batch-size 16`, đồng thời giảm số ảnh nếu cần: loader hiện vẫn giữ toàn bộ ảnh train/val trong RAM. Mỗi lần thử cấu hình khác dùng thư mục mới (`run02`, `run03`); script từ chối ghi vào thư mục đầu ra đã có nội dung.

Pipeline tự lưu model Keras, export SavedModel rồi chuyển INT8 với dữ liệu calibration lấy **chỉ từ train**, có cả hai lớp. Không cần sửa thủ công `model.save()` như script cũ.

## 6. Kiểm tra các file đầu ra

Sau khi train và convert thành công:

```text
ai_model/output/run01/
├── parking_cnn.keras             # Model float, checkpoint tốt nhất
├── parking_cnn_saved_model/      # Bản export dùng để chuyển đổi
├── parking_cnn_int8.tflite        # Model INT8
├── model_data.h                  # Mảng C tương ứng model INT8
├── history.csv                   # Loss, accuracy, AUC theo epoch
├── validation_float.json         # Kết quả float trên val ở ngưỡng mặc định
├── dataset_manifest.json         # Nhãn, preprocessing, đường dẫn, hash train/val
├── run_config.json               # Cấu hình và phiên bản TensorFlow/NumPy
└── quantization.json             # Scale, zero-point, shape, kích thước model
```

Mở `history.csv` bằng Excel và vẽ `loss` cùng `val_loss` theo epoch để quan sát overfit. Chưa được coi là kiểm thử hoàn tất chỉ vì đã có file `.tflite`.

## 7. Chọn ngưỡng bằng validation

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\evaluate_model.py --model-dir ai_model\output\run01 --data-dir ai_model\dataset\val --split val --threshold 0.5 --report-dir ai_model\output\run01\validation
```

Lệnh đánh giá cả float và INT8 tại ngưỡng 0.5, đồng thời thử ngưỡng INT8 từ 0.05 đến 0.95 với bước 0.05. Gợi ý ngưỡng có F1 lớp có xe cao nhất được ghi trong `metrics.json` ở trường `recommended_int8_threshold_from_validation`; khi bằng F1, ưu tiên precision cao hơn.

Lấy ngưỡng gợi ý vào biến PowerShell:

```powershell
$validationReport = Get-Content ai_model\output\run01\validation\metrics.json -Raw | ConvertFrom-Json
$threshold = $validationReport.recommended_int8_threshold_from_validation
$threshold
```

Xem `validation/threshold_candidates.csv` nếu cần ưu tiên precision hoặc recall thay cho F1. Khi đó tự chọn ngưỡng từ validation và gán `$threshold = ...`. Không dùng test để chọn ngưỡng.

## 8. Đánh giá cuối cùng trên test

Giữ nguyên `$threshold` đã chọn và chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\evaluate_model.py --model-dir ai_model\output\run01 --data-dir ai_model\dataset\test --split test --threshold $threshold --report-dir ai_model\output\run01\test
```

Script từ chối nếu phát hiện ảnh test giống hệt ảnh train hoặc val. Nó tạo `test/metrics.json` và `test/predictions.csv`.

| Kết quả | Cách hiểu |
|---|---|
| TP | Có xe, dự đoán có xe |
| TN | Không có xe, dự đoán không có xe |
| FP | Không có xe nhưng báo có xe |
| FN | Có xe nhưng báo không có xe |
| Precision lớp xe | Trong các lần báo có xe, tỷ lệ đúng |
| Recall lớp xe | Trong các ảnh có xe, tỷ lệ phát hiện được |
| F1 lớp xe | Cân bằng precision và recall |
| False positive rate | Tỷ lệ ảnh không có xe bị báo thành có xe |

So sánh các chỉ số `float` và `int8` trong cùng báo cáo. `prediction_disagreements` là số ảnh hai model ra quyết định khác nhau; `mean_absolute_score_difference` là độ lệch điểm trung bình, không phải độ giảm accuracy.

Ví dụ minh họa: test có 200 ảnh có xe và 200 ảnh không có xe. Nếu TP=190, FN=10, TN=194, FP=6 thì accuracy=96%, precision≈96,9%, recall=95%. Đây là ví dụ tính toán, không phải kết quả dự kiến của project.

Bạn có thể đặt mục tiêu học tập ban đầu như precision/recall đều >=90% và INT8 giảm không quá 1–2 điểm phần trăm so với float. Đây là tiêu chí tự đặt, không phải chuẩn bắt buộc hoặc bảo đảm của kiến trúc. Mục tiêu cần phản ánh độ khó của cách chia test.

Mở `predictions.csv`, lọc `int8_correct = 0`, xem các ảnh lỗi để mô tả hạn chế: bóng đổ, che khuất, góc nhìn, xe nhỏ, crop sai hoặc nhãn sai. Nếu dùng các lỗi test để sửa model, tập đó đã trở thành dữ liệu phát triển; cần test mới hoặc báo rõ quy trình, không coi việc liên tục tối ưu trên cùng test là đánh giá độc lập.

## 9. Thử một ảnh mới

Ảnh phải chứa một ô đỗ. Thay đường dẫn minh họa sau bằng ảnh của bạn:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\evaluate_model.py --model-dir ai_model\output\run01 --image "D:\images\parking_slot.jpg" --threshold $threshold
```

Lệnh in điểm có xe và nhãn của cả float/INT8. Điểm 0.9 không bảo đảm dự đoán đúng 90%. Thử vài ảnh chỉ là kiểm tra thủ công, không thay thế test có nhãn.

## 10. Chuẩn bị bước chạy ESP32

Sau khi chấp nhận kết quả, xuất header vào firmware:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\tflite_to_c_array.py ai_model\output\run01\parking_cnn_int8.tflite firmware_esp32\esp32_parking_inference\model_data.h
```

Lệnh ghi đè header model trong firmware. Ghi lại `$threshold` và cấu hình ngưỡng gateway qua `--threshold` hoặc báo cáo validation; ngưỡng được gửi sang ESP32 trong `X-Threshold`.

Trước khi nạp, cần xử lý các giới hạn firmware đã ghi trong README: chuẩn hóa đầu vào, crop/resize, tensor arena và tương thích TFLite Micro. Đầu vào model này dùng pixel `0–255`:

```text
q = clamp(round(pixel / input_scale) + input_zero_point, -128, 127)
score = (output_int8 - output_zero_point) × output_scale
```

Không chia 255 thêm trước công thức lượng tử hóa vì model đã chứa Rescaling. Gateway dùng chung preprocessing với train và gửi ảnh uint8 64×64; firmware chỉ lượng tử hóa rồi suy luận. Xem `docs/system_architecture.md`.

Kiểm thử thiết bị cần xác nhận `AllocateTensors()`/`Invoke()` thành công, đo RAM và thời gian thực tế, rồi so sánh điểm Python/ESP32 trên cùng ảnh đã tiền xử lý. File model nhỏ không tự bảo đảm đủ RAM. Kết quả dataset công khai chưa chứng minh model hoạt động tốt trên sa bàn có góc nhìn khác.

## Tài liệu kỹ thuật tham khảo

- [Keras: lưu và nạp model](https://keras.io/guides/serialization_and_saving/)
- [Google AI Edge: lượng tử hóa toàn phần integer](https://developers.google.com/edge/litert/conversion/tensorflow/quantization/post_training_integer_quant)

Hướng dẫn này mô tả quy trình chạy. Chưa có kết quả train/test thật nếu chưa cung cấp dataset và chạy các lệnh tương ứng.
