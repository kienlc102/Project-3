"""Train a custom parking CNN on explicit train/val splits and export INT8."""

import argparse
import json
import platform
from pathlib import Path


def configure_device(tf, device="auto"):
    """Configure GPU before creating tensors; keep float32 for INT8 export."""
    if device not in ("auto", "gpu", "cpu"):
        raise ValueError("device must be auto, gpu, or cpu")
    if device == "cpu":
        tf.config.set_visible_devices([], "GPU")
        print("[DEVICE] CPU requested.")
        return {"requested": device, "selected": "cpu", "name": platform.processor()}
    gpus = tf.config.list_physical_devices("GPU")
    if not gpus:
        message = "TensorFlow cannot detect a CUDA GPU."
        if platform.system() == "Windows":
            message += (" TensorFlow >=2.11 does not support CUDA on native Windows. "
                        "Use Ubuntu on WSL2 and install ai_model/requirements-gpu.txt. "
                        "See docs/gpu_training.md.")
        else:
            message += " Check nvidia-smi and install ai_model/requirements-gpu.txt in this Linux environment."
        if device == "gpu":
            raise RuntimeError(message + " GPU was required; training has not started.")
        print(f"[DEVICE] {message} Falling back to CPU (--device auto).")
        return {"requested": device, "selected": "cpu", "name": platform.processor()}
    # One GPU is sufficient for this model and the 4 GB RTX 3050 Ti.
    gpu = gpus[0]
    tf.config.set_visible_devices([gpu], "GPU")
    tf.config.experimental.set_memory_growth(gpu, True)
    details = tf.config.experimental.get_device_details(gpu)
    name = details.get("device_name", gpu.name)
    print(f"[DEVICE] GPU: {name}; memory growth enabled; float32 training.")
    return {"requested": device, "selected": "gpu", "name": name, "memory_growth": True}


def check_device(device):
    import tensorflow as tf
    info = configure_device(tf, device)
    target = "/GPU:0" if info["selected"] == "gpu" else "/CPU:0"
    with tf.device(target):
        result = tf.matmul(tf.ones((32, 32)), tf.ones((32, 32)))
    result.numpy()  # Wait for the operation to finish.
    if info["selected"] == "gpu" and "GPU:0" not in result.device.upper():
        raise RuntimeError(f"GPU probe unexpectedly ran on {result.device}")
    print(f"[CHECK] Matrix multiplication ran on {result.device}")


def make_training_datasets(tf, X_train, y_train, X_val, y_val, batch_size, seed):
    # Keep the source images uint8 in host RAM. Keras casts model inputs to float32.
    train = tf.data.Dataset.from_tensor_slices((X_train, y_train))
    train = train.shuffle(min(len(X_train), 4096), seed=seed, reshuffle_each_iteration=True)
    train = train.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    val = tf.data.Dataset.from_tensor_slices((X_val, y_val)).batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return train, val


def train_and_quantize(epochs=40, batch_size=32, dataset_dir="dataset", output_dir="output", seed=42,
                       export_firmware=False, device="auto"):
    import numpy as np
    import tensorflow as tf
    device_info = configure_device(tf, device)
    tf.keras.mixed_precision.set_global_policy("float32")
    from dataset_io import load_dataset, image_hashes, reject_overlap
    from model import build_ultralight_parking_cnn
    from tflite_to_c_array import convert_tflite_to_c_array

    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch_size must be positive")
    tf.keras.utils.set_random_seed(seed)
    dataset_dir, output_dir = Path(dataset_dir), Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory is not empty: {output_dir}. Use a new run directory.")
    X_train, y_train, train_paths = load_dataset(dataset_dir / "train")
    X_val, y_val, val_paths = load_dataset(dataset_dir / "val")
    train_hashes, val_hashes = image_hashes(X_train), image_hashes(X_val)
    reject_overlap(train_hashes, val_hashes, "Train vs validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "labels": {"vacant": 0, "occupied": 1},
        "preprocessing": "EXIF orientation, grayscale, center square crop, bilinear 64x64, pixel 0..255",
        "seed": seed, "train_paths": train_paths, "val_paths": val_paths,
        "train_hashes": train_hashes, "val_hashes": val_hashes,
    }
    (output_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "run_config.json").write_text(json.dumps({
        "epochs": epochs, "batch_size": batch_size, "seed": seed,
        "dataset_dir": str(dataset_dir.resolve()), "tensorflow": tf.__version__,
        "numpy": np.__version__, "train_images": len(X_train), "val_images": len(X_val),
        "device": device_info,
    }, indent=2), encoding="utf-8")

    model = build_ultralight_parking_cnn()
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss="binary_crossentropy", metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
                  jit_compile=False)
    model.summary()
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=7, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5),
        tf.keras.callbacks.CSVLogger(str(output_dir / "history.csv")),
        tf.keras.callbacks.ModelCheckpoint(str(output_dir / "parking_cnn.keras"),
                                           monitor="val_loss", save_best_only=True),
    ]
    train_dataset, val_dataset = make_training_datasets(tf, X_train, y_train, X_val, y_val, batch_size, seed)
    model.fit(train_dataset, validation_data=val_dataset, epochs=epochs, callbacks=callbacks, shuffle=False, verbose=1)
    # Reload the persisted best epoch, including when training reaches the epoch limit.
    model = tf.keras.models.load_model(output_dir / "parking_cnn.keras")
    val_metrics = model.evaluate(val_dataset, verbose=0, return_dict=True)
    (output_dir / "validation_float.json").write_text(json.dumps(val_metrics, indent=2), encoding="utf-8")
    model.export(str(output_dir / "parking_cnn_saved_model"))

    # Sample both classes from TRAIN only, for representative calibration.
    rng = np.random.default_rng(seed)
    calibration = np.concatenate([rng.permutation(np.flatnonzero(y_train == label))[:75]
                                  for label in (0, 1)])
    rng.shuffle(calibration)

    def representative_dataset():
        for index in calibration:
            yield [X_train[index:index + 1].astype(np.float32)]

    converter = tf.lite.TFLiteConverter.from_saved_model(str(output_dir / "parking_cnn_saved_model"))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_path = output_dir / "parking_cnn_int8.tflite"
    tflite_path.write_bytes(converter.convert())
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    tensor_info = {}
    for name, detail in (("input", interpreter.get_input_details()[0]),
                         ("output", interpreter.get_output_details()[0])):
        scale, zero = detail["quantization"]
        if detail["dtype"] != np.int8 or scale <= 0:
            raise ValueError(f"Invalid INT8 {name}: {detail}")
        tensor_info[name] = {"shape": detail["shape"].tolist(), "dtype": "int8",
                             "scale": float(scale), "zero_point": int(zero)}
    tensor_info["model_bytes"] = tflite_path.stat().st_size
    tensor_info["input_formula"] = "clip(round(pixel_0_to_255 / input_scale) + input_zero_point, -128, 127)"
    (output_dir / "quantization.json").write_text(json.dumps(tensor_info, indent=2), encoding="utf-8")
    convert_tflite_to_c_array(str(tflite_path), str(output_dir / "model_data.h"))
    if export_firmware:
        firmware_header = Path(__file__).resolve().parent.parent / "firmware_esp32" / "esp32_parking_inference" / "model_data.h"
        firmware_header.parent.mkdir(parents=True, exist_ok=True)
        convert_tflite_to_c_array(str(tflite_path), str(firmware_header))
    print(f"Artifacts: {output_dir.resolve()}")
    print("Next: choose a threshold on validation, then evaluate FLOAT and INT8 on held-out test.")
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default="dataset")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "gpu", "cpu"], default="auto",
                        help="auto selects GPU if available; gpu fails early when unavailable")
    parser.add_argument("--check-device", action="store_true", help="Probe device placement without loading data or training")
    parser.add_argument("--export-firmware", action="store_true", help="Overwrite firmware model_data.h after conversion")
    args = parser.parse_args()
    if args.check_device:
        check_device(args.device)
    else:
        options = vars(args)
        options.pop("check_device")
        train_and_quantize(**options)


if __name__ == "__main__":
    main()
