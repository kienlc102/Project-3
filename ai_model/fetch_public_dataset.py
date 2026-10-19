"""
Fetch & Prepare Public Dataset from Online Repositories / Roboflow / Open Datasets
Công cụ hỗ trợ tải, lọc và chuẩn hóa tập dữ liệu có sẵn trên mạng về chuẩn 64x64 Grayscale
phù hợp với vi điều khiển ESP32-CAM và sa bàn bãi đỗ xe.
"""

import os
import sys
import glob
import urllib.request
import zipfile
import shutil
from PIL import Image


def download_and_extract(url, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "temp_download.zip")
    print(f"[DOWNLOAD] Đang tải dataset từ: {url}...")
    
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    urllib.request.install_opener(opener)
    
    urllib.request.urlretrieve(url, zip_path)
    print(f"[EXTRACT] Đang giải nén vào {target_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_dir)
    os.remove(zip_path)
    print("[SUCCESS] Giải nén thành công!")


def preprocess_folder_to_grayscale(src_dir, dest_dir, img_size=(64, 64), max_samples=800):
    """
    Duyệt toàn bộ ảnh trong thư mục nguồn, crop về hình vuông, resize 64x64,
    chuyển sang Grayscale (L) và lưu vào dest_dir.
    """
    os.makedirs(dest_dir, exist_ok=True)
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
    found_files = []
    for ext in extensions:
        found_files.extend(glob.glob(os.path.join(src_dir, "**", ext), recursive=True))
        
    print(f"[PREPROCESS] Tìm thấy {len(found_files)} ảnh tại '{src_dir}'. Đang xử lý tối đa {max_samples} ảnh...")
    
    saved = 0
    for file_path in found_files:
        if saved >= max_samples:
            break
        try:
            with Image.open(file_path) as img:
                # 1. Chuyển sang ảnh xám 8-bit (Grayscale)
                gray_img = img.convert("L")
                
                # 2. Center-crop về tỉ lệ 1:1 hình vuông trước khi resize để không làm méo vật thể
                w, h = gray_img.size
                min_dim = min(w, h)
                left = (w - min_dim) // 2
                top = (h - min_dim) // 2
                cropped = gray_img.crop((left, top, left + min_dim, top + min_dim))
                
                # 3. Resize về chuẩn 64x64 theo kiến trúc CNN
                resized = cropped.resize(img_size, Image.Resampling.LANCZOS)
                
                out_name = f"sample_{saved:04d}.jpg"
                resized.save(os.path.join(dest_dir, out_name), "JPEG", quality=90)
                saved += 1
        except Exception as e:
            continue
            
    print(f"[HOÀN TẤT] Đã chuẩn hóa {saved} ảnh vào '{dest_dir}' (64x64 Grayscale).")
    return saved


if __name__ == "__main__":
    print("=== HƯỚNG DẪN NẠP DATASET TỪ INTERNET ===")
    print("1. Tải ảnh từng ô đỗ có xe / không có xe từ CNRPark hoặc PKLot.")
    print("2. Đặt ảnh thô vào:")
    print("   - raw_data/occupied/ (Ảnh ô đỗ có xe, nhãn 1)")
    print("   - raw_data/vacant/ (Ảnh ô đỗ không có xe, nhãn 0)")
    print("3. Chạy lệnh: python fetch_public_dataset.py --process")
    print("Script sẽ tự động resize về 64x64 Grayscale chuẩn vào thư mục dataset/.")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--process":
        preprocess_folder_to_grayscale("raw_data/occupied", "dataset/occupied")
        preprocess_folder_to_grayscale("raw_data/vacant", "dataset/vacant")
        print("\n[THÀNH CÔNG] Giờ bạn có thể chạy 'python train_and_quantize.py' để huấn luyện mô hình!")
