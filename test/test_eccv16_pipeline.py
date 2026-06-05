"""
End-to-end pipeline test: FFmpeg decode -> ECCV16 colorize -> FFmpeg encode
Uses the same byte-accumulation approach as the controller.
"""
import os
import sys
import subprocess
import numpy as np
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'PySide6'))

from colorizers.eccv16 import ECCV16

WEIGHT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'PySide6', 'colorizers', 'models',
    'colorization_release_v2-9b330a0b.pth'
)

FFMPEG = "/usr/bin/ffmpeg"
INPUT = "/tmp/test_gray_video.mp4"
OUTPUT = "/tmp/test_colorized_pipe_output.mp4"
W, H = 640, 360
FPS = 30.0
BATCH_SIZE = 8


def run_pipeline():
    if not os.path.isfile(INPUT):
        print(f"Input video not found: {INPUT}")
        return False
    if not os.path.isfile(WEIGHT_PATH):
        print(f"Weights not found: {WEIGHT_PATH}")
        return False

    colorizer = ECCV16(weight_path=WEIGHT_PATH, device="cpu", fp16=False, batch_size=BATCH_SIZE)
    frame_size_luma = W * H

    decode_cmd = [
        FFMPEG, "-i", INPUT,
        "-f", "rawvideo", "-pix_fmt", "gray",
        "-s", f"{W}x{H}", "-r", str(FPS),
        "-vcodec", "rawvideo", "-an", "-sn",
        "-"
    ]
    encode_cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-i", INPUT,
        "-map", "0:v", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        "-shortest",
        OUTPUT
    ]

    decode_proc = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    encode_proc = subprocess.Popen(
        encode_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    batch_buffer = []
    frames_total = 0
    t_start = time.time()
    stream = decode_proc.stdout
    buf = b""

    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        buf += chunk
        while len(buf) >= frame_size_luma:
            frame_data = buf[:frame_size_luma]
            buf = buf[frame_size_luma:]
            luma = np.frombuffer(frame_data, dtype=np.uint8).reshape(H, W)
            luma_norm = luma.astype(np.float32) / 255.0
            batch_buffer.append(luma_norm)
            if len(batch_buffer) >= BATCH_SIZE:
                batch_arr = np.stack(batch_buffer, axis=0)
                rgb_batch = colorizer.colorize_batch(batch_arr)
                for frame in rgb_batch:
                    encode_proc.stdin.write(frame.tobytes())
                frames_total += len(batch_buffer)
                batch_buffer = []

    if batch_buffer:
        batch_arr = np.stack(batch_buffer, axis=0)
        rgb_batch = colorizer.colorize_batch(batch_arr)
        for frame in rgb_batch:
            encode_proc.stdin.write(frame.tobytes())
        frames_total += len(batch_buffer)

    encode_proc.stdin.close()
    decode_proc.wait()
    encode_proc.wait()

    elapsed = time.time() - t_start
    fps_effective = frames_total / elapsed if elapsed > 0 else 0

    if encode_proc.returncode == 0 and os.path.exists(OUTPUT):
        out_size = os.path.getsize(OUTPUT)
        print(f"PASS: {frames_total} frames colorized in {elapsed:.1f}s ({fps_effective:.1f} fps)")
        print(f"      Output: {OUTPUT} ({out_size} bytes)")
        return True
    else:
        print(f"FAIL: decode={decode_proc.returncode}, encode={encode_proc.returncode}")
        return False


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
