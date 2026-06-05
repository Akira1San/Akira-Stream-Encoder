import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'PySide6'))

from colorizers.eccv16 import ECCV16, ECCVGenerator
from colorizers.utils import lab_to_rgb, rgb_to_lab, luma_to_rgb, raw_luma_to_numpy, apply_saturation


WEIGHT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'PySide6', 'colorizers', 'models',
    'colorization_release_v2-9b330a0b.pth'
)


def test_model_architecture():
    model = ECCVGenerator()
    assert model is not None
    # Forward pass with random input
    x = np.random.randn(1, 1, 224, 224).astype(np.float32)
    x_t = __import__('torch').from_numpy(x)
    with __import__('torch').no_grad():
        out = model(x_t)
    assert out.shape == (1, 2, 224, 224), f"Unexpected output shape: {out.shape}"
    print(f"  Model forward OK, output shape: {out.shape}")


def test_colorizer_init():
    assert os.path.isfile(WEIGHT_PATH), f"Weights not found: {WEIGHT_PATH}"
    colorizer = ECCV16(weight_path=WEIGHT_PATH, device="cpu", fp16=False, batch_size=4)
    assert colorizer.name() == "eccv16"
    assert colorizer.supports_batch() is True
    print(f"  Colorizer init OK, device={colorizer._device}")


def test_colorize_single_frame():
    colorizer = ECCV16(weight_path=WEIGHT_PATH, device="cpu", fp16=False, batch_size=4)
    H, W = 256, 256
    l_channel = np.random.rand(H, W).astype(np.float32)
    rgb = colorizer.colorize_frame(l_channel)
    assert rgb.shape == (H, W, 3)
    assert rgb.dtype == np.uint8
    print(f"  Single frame OK, shape={rgb.shape}, dtype={rgb.dtype}, min={rgb.min()}, max={rgb.max()}")


def test_colorize_batch():
    colorizer = ECCV16(weight_path=WEIGHT_PATH, device="cpu", fp16=False, batch_size=4)
    B, H, W = 4, 256, 256
    batch = np.random.rand(B, H, W).astype(np.float32)
    rgb_batch = colorizer.colorize_batch(batch)
    assert rgb_batch.shape == (B, H, W, 3)
    assert rgb_batch.dtype == np.uint8
    print(f"  Batch {B} frames OK, shape={rgb_batch.shape}")


def test_utils_lab_rgb_roundtrip():
    rgb = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
    lab = rgb_to_lab(rgb)
    assert lab.shape == (64, 64, 3)
    assert lab.dtype == np.float32
    rgb2 = lab_to_rgb(lab)
    assert rgb2.shape == (64, 64, 3)
    assert rgb2.dtype == np.uint8
    # Approximate roundtrip (Lab->RGB->Lab is lossy but should be close)
    diff = np.abs(rgb.astype(np.int16) - rgb2.astype(np.int16)).mean()
    assert diff < 30, f"Lab->RGB roundtrip diff too large: {diff}"
    print(f"  Lab-RGB roundtrip OK, mean diff={diff:.2f}")


def test_utils_luma_to_rgb():
    H, W = 64, 64
    l_channel = np.random.rand(H, W).astype(np.float32)
    ab = np.random.rand(H, W, 2).astype(np.float32) * 20 - 10
    rgb = luma_to_rgb(l_channel, ab)
    assert rgb.shape == (H, W, 3)
    assert rgb.dtype == np.uint8
    print(f"  luma_to_rgb OK, shape={rgb.shape}")


def test_utils_saturation():
    rgb = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
    sat = apply_saturation(rgb, 1.5)
    assert sat.shape == rgb.shape
    assert sat.dtype == np.uint8
    sat0 = apply_saturation(rgb, 0.0)
    assert sat0.shape == rgb.shape
    print(f"  Saturation OK (1.5x and 0.0x)")


def test_raw_luma_roundtrip():
    H, W = 64, 64
    original = np.random.randint(0, 256, (H, W), dtype=np.uint8)
    raw_bytes = original.tobytes()
    reconstructed = raw_luma_to_numpy(raw_bytes, W, H)
    assert reconstructed.shape == (H, W)
    assert reconstructed.dtype == np.float32
    back_to_uint8 = (reconstructed * 255).astype(np.uint8)
    assert np.array_equal(original, back_to_uint8)
    print(f"  Raw luma roundtrip OK")


if __name__ == "__main__":
    import traceback
    tests = [
        ("Model architecture", test_model_architecture),
        ("Colorizer init", test_colorizer_init),
        ("Colorize single frame", test_colorize_single_frame),
        ("Colorize batch", test_colorize_batch),
        ("Lab-RGB roundtrip", test_utils_lab_rgb_roundtrip),
        ("Luma to RGB", test_utils_luma_to_rgb),
        ("Saturation", test_utils_saturation),
        ("Raw luma roundtrip", test_raw_luma_roundtrip),
    ]
    failed = 0
    for name, fn in tests:
        print(f"  [{name}]...", end=" ", flush=True)
        try:
            fn()
            print("PASS")
        except Exception as e:
            print("FAIL")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    if failed:
        print(f"FAILED: {failed}/{len(tests)} tests")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
