"""
Single image colorization test for ECCV16 and SIGGRAPH17.
Usage: python3 test_colorize_image.py [input_image] -o output.png --engine siggraph17

If no input image is provided, creates a synthetic test pattern.
"""
import sys
import os
import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'PySide6'))

from colorizers.eccv16 import ECCV16
from colorizers.siggraph17 import SIGGRAPH17
from colorizers.utils import apply_postprocessing


def get_weight_path(engine: str) -> str:
    weights = {
        "eccv16": "colorization_release_v2-9b330a0b.pth",
        "siggraph17": "siggraph17-df00044c.pth",
    }
    return os.path.join(
        os.path.dirname(__file__), '..', 'PySide6', 'colorizers', 'models',
        weights[engine]
    )


def colorize_image(input_path: str, output_path: str,
                   saturation: float = 1.0, contrast: float = 1.0,
                   denoise: float = 0.0, device: str = "cpu",
                   engine: str = "eccv16"):
    """Colorize a single grayscale image and save the result."""
    weight_path = get_weight_path(engine)
    if not os.path.isfile(weight_path):
        print(f"ERROR: Weights not found at {weight_path}")
        return False

    if input_path and os.path.isfile(input_path):
        img = cv2.imread(input_path)
        if img is None:
            print(f"ERROR: Could not read {input_path}")
            return False
        if len(img.shape) == 3 and img.shape[2] == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            print(f"Read {input_path}: {gray.shape[1]}x{gray.shape[0]}, converted to grayscale")
        else:
            gray = img
            print(f"Read {input_path}: {gray.shape[1]}x{gray.shape[0]}, already grayscale")
    else:
        H, W = 360, 640
        gray = np.zeros((H, W), dtype=np.uint8)
        cv2.rectangle(gray, (50, 50), (W-50, H-50), 200, -1)
        cv2.rectangle(gray, (200, 100), (440, 260), 80, -1)
        cv2.putText(gray, "AI Colorization Test", (120, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
        for i in range(H):
            gray[i, :] = int(255 * i / H)
        print("Created synthetic test pattern")

    luma_norm = gray.astype(np.float32) / 255.0

    print(f"Colorizing with {engine} (device={device}, sat={saturation}, "
          f"contrast={contrast}, denoise={denoise})...")
    if engine == "eccv16":
        colorizer = ECCV16(weight_path=weight_path, device=device, fp16=False, batch_size=1)
    elif engine == "siggraph17":
        colorizer = SIGGRAPH17(weight_path=weight_path, device=device, fp16=False, batch_size=1)
    else:
        print(f"Unknown engine: {engine}")
        return False
    rgb = colorizer.colorize_frame(luma_norm)

    if saturation != 1.0 or contrast != 1.0 or denoise > 0.0:
        rgb = apply_postprocessing(rgb, saturation, contrast, denoise)

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(output_path, bgr)
    print(f"Saved colorized image to {output_path}")
    print(f"  Input:  {gray.shape[1]}x{gray.shape[0]} grayscale")
    print(f"  Output: {rgb.shape[1]}x{rgb.shape[0]} RGB (range {rgb.min()}-{rgb.max()})")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Colorize a single image with AI")
    parser.add_argument("input", nargs="?", default="",
                        help="Input grayscale image (creates test pattern if omitted)")
    parser.add_argument("-o", "--output", default="/tmp/colorized_output.png",
                        help="Output image path (default: /tmp/colorized_output.png)")
    parser.add_argument("--saturation", type=float, default=1.2,
                        help="Saturation boost (0.1-2.0, default: 1.2)")
    parser.add_argument("--contrast", type=float, default=1.0,
                        help="Contrast adjustment (0.5-2.0, default: 1.0)")
    parser.add_argument("--denoise", type=float, default=0.0,
                        help="Denoise strength (0-5, default: 0)")
    parser.add_argument("--device", default="cpu",
                        help="Device: cpu or cuda:0 (default: cpu)")
    parser.add_argument("--engine", default="eccv16",
                        choices=["eccv16", "siggraph17"],
                        help="Colorization engine (default: eccv16)")
    args = parser.parse_args()

    success = colorize_image(
        args.input, args.output,
        saturation=args.saturation,
        contrast=args.contrast,
        denoise=args.denoise,
        device=args.device,
        engine=args.engine,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
