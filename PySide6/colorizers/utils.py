import numpy as np


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """Convert Lab float32 array (HxWx3) to RGB uint8 array (HxWx3)."""
    lab = lab.astype(np.float32)
    rng = 255.0
    L = lab[:, :, 0]
    a = lab[:, :, 1]
    b = lab[:, :, 2]

    y = (L + 16.0) / 116.0
    x = (a / 500.0) + y
    z = y - (b / 200.0)

    def f(t):
        t3 = t ** 3
        return np.where(t3 > 0.008856, t3, (t - 16.0 / 116.0) / 7.787)

    x_r = 0.95047 * f(x)
    y_r = 1.00000 * f(y)
    z_r = 1.08883 * f(z)

    r = 3.2404542 * x_r - 1.5371385 * y_r - 0.4985314 * z_r
    g = -0.9692660 * x_r + 1.8760108 * y_r + 0.0415560 * z_r
    b_ = 0.0556434 * x_r - 0.2040259 * y_r + 1.0572252 * z_r

    rgb = np.stack([r, g, b_], axis=-1)
    rgb = np.clip(rgb, 0.0, 1.0)
    return (rgb * rng).astype(np.uint8)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert RGB uint8 array (HxWx3) to Lab float32 array (HxWx3)."""
    rgb = rgb.astype(np.float32) / 255.0

    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    x /= 0.95047
    y /= 1.00000
    z /= 1.08883

    def f(t):
        return np.where(t > 0.008856, t ** (1.0 / 3.0), 7.787 * t + 16.0 / 116.0)

    fx = f(x)
    fy = f(y)
    fz = f(z)

    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b_ = 200.0 * (fy - fz)

    return np.stack([L, a, b_], axis=-1).astype(np.float32)


def luma_to_rgb(l_channel: np.ndarray, ab: np.ndarray) -> np.ndarray:
    """Combine L channel (HxW float32 0-1 normalized) with ab channels (HxWx2)
    and convert to RGB uint8. L is assumed to be in [0,1] range (normalized),
    ab is in model-output range (approximately [-110, 110])."""
    L_lab = l_channel * 100.0
    lab = np.concatenate([L_lab[:, :, np.newaxis], ab], axis=-1)
    return lab_to_rgb(lab)


def raw_luma_to_numpy(bytes_data: bytes, width: int, height: int) -> np.ndarray:
    """Convert raw luma bytes from FFmpeg rawvideo to normalized float32 array (HxW 0-1)."""
    arr = np.frombuffer(bytes_data, dtype=np.uint8).reshape(height, width)
    return arr.astype(np.float32) / 255.0


def numpy_to_rgb_bytes(frame: np.ndarray) -> bytes:
    """Convert RGB uint8 numpy array (HxWx3) to raw bytes for FFmpeg rawvideo."""
    return frame.tobytes()


def apply_saturation(rgb: np.ndarray, saturation: float) -> np.ndarray:
    """Adjust saturation of RGB uint8 image. 1.0 = no change."""
    if abs(saturation - 1.0) < 1e-6:
        return rgb
    lab = rgb_to_lab(rgb)
    a = lab[:, :, 1] * saturation
    b = lab[:, :, 2] * saturation
    lab[:, :, 1] = np.clip(a, -128, 127)
    lab[:, :, 2] = np.clip(b, -128, 127)
    return lab_to_rgb(lab)


def apply_contrast(rgb: np.ndarray, contrast: float) -> np.ndarray:
    """Adjust contrast of RGB uint8 image. 1.0 = no change."""
    if abs(contrast - 1.0) < 1e-6:
        return rgb
    factor = (259.0 * (contrast * 127.5 + 127.5)) / (255.0 * (259.0 - contrast * 127.5 - 127.5))
    arr = rgb.astype(np.float32)
    arr = factor * (arr - 128.0) + 128.0
    return np.clip(arr, 0, 255).astype(np.uint8)


def apply_denoise(rgb: np.ndarray, strength: float) -> np.ndarray:
    """Apply light bilateral/median denoise. strength 0-5, 0 = off."""
    if strength < 0.5:
        return rgb
    import cv2
    k = int(strength) * 2 + 1
    if k < 3:
        return rgb
    return cv2.bilateralFilter(rgb, k, strength * 20, strength * 20)


def apply_postprocessing(rgb: np.ndarray, saturation: float = 1.0,
                          contrast: float = 1.0, denoise: float = 0.0) -> np.ndarray:
    """Apply all post-processing steps in optimal order."""
    result = rgb
    if denoise > 0.0:
        result = apply_denoise(result, denoise)
    if saturation != 1.0:
        result = apply_saturation(result, saturation)
    if contrast != 1.0:
        result = apply_contrast(result, contrast)
    return result
