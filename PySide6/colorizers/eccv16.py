import os
import torch
import torch.nn as nn
import numpy as np

from colorizers.base import Colorizer
from colorizers.utils import apply_saturation, luma_to_rgb


MODEL_URL = "https://colorizers.s3.us-east-2.amazonaws.com/colorization_release_v2-9b330a0b.pth"


class BaseColor(nn.Module):
    def __init__(self):
        super().__init__()
        self.l_cent = 50.0
        self.l_norm = 100.0
        self.ab_norm = 110.0

    def normalize_l(self, in_l):
        return (in_l - self.l_cent) / self.l_norm

    def unnormalize_l(self, in_l):
        return in_l * self.l_norm + self.l_cent

    def normalize_ab(self, in_ab):
        return in_ab / self.ab_norm

    def unnormalize_ab(self, in_ab):
        return in_ab * self.ab_norm


class ECCVGenerator(BaseColor):
    def __init__(self, norm_layer=nn.BatchNorm2d):
        super().__init__()

        model1 = [
            nn.Conv2d(1, 64, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1, bias=True),
            nn.ReLU(True),
            norm_layer(64),
        ]

        model2 = [
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(128, 128, kernel_size=3, stride=2, padding=1, bias=True),
            nn.ReLU(True),
            norm_layer(128),
        ]

        model3 = [
            nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(256, 256, kernel_size=3, stride=2, padding=1, bias=True),
            nn.ReLU(True),
            norm_layer(256),
        ]

        model4 = [
            nn.Conv2d(256, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            norm_layer(512),
        ]

        model5 = [
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            norm_layer(512),
        ]

        model6 = [
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, dilation=2, stride=1, padding=2, bias=True),
            nn.ReLU(True),
            norm_layer(512),
        ]

        model7 = [
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            norm_layer(512),
        ]

        model8 = [
            nn.ConvTranspose2d(512, 256, kernel_size=4, stride=2, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1, bias=True),
            nn.ReLU(True),
            nn.Conv2d(256, 313, kernel_size=1, stride=1, padding=0, bias=True),
        ]

        self.model1 = nn.Sequential(*model1)
        self.model2 = nn.Sequential(*model2)
        self.model3 = nn.Sequential(*model3)
        self.model4 = nn.Sequential(*model4)
        self.model5 = nn.Sequential(*model5)
        self.model6 = nn.Sequential(*model6)
        self.model7 = nn.Sequential(*model7)
        self.model8 = nn.Sequential(*model8)

        self.softmax = nn.Softmax(dim=1)
        self.model_out = nn.Conv2d(313, 2, kernel_size=1, padding=0, dilation=1, stride=1, bias=False)
        self.upsample4 = nn.Upsample(scale_factor=4, mode='bilinear')

    def forward(self, input_l):
        conv1_2 = self.model1(self.normalize_l(input_l))
        conv2_2 = self.model2(conv1_2)
        conv3_3 = self.model3(conv2_2)
        conv4_3 = self.model4(conv3_3)
        conv5_3 = self.model5(conv4_3)
        conv6_3 = self.model6(conv5_3)
        conv7_3 = self.model7(conv6_3)
        conv8_3 = self.model8(conv7_3)
        out_reg = self.model_out(self.softmax(conv8_3))
        return self.unnormalize_ab(self.upsample4(out_reg))


class ECCV16(Colorizer):
    """ECCV16 colorizer (Zhang et al. 2016). Lightweight CNN, runs on CPU/GPU."""

    def __init__(self, weight_path: str, device: str = "cuda:0", fp16: bool = True, batch_size: int = 8):
        self._weight_path = weight_path
        self._device = torch.device(device if torch.cuda.is_available() and "cuda" in device else "cpu")
        self._fp16 = fp16 and self._device.type == "cuda"
        self._batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        if not os.path.isfile(self._weight_path):
            raise FileNotFoundError(
                f"ECCV16 weights not found at: {self._weight_path}\n"
                f"Download from: {MODEL_URL}"
            )
        model = ECCVGenerator()
        state_dict = torch.load(self._weight_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict, strict=False)
        model.eval()
        model.to(self._device)
        if self._fp16:
            model = model.half()
        self._model = model

    def _prepare_input(self, l_channel: np.ndarray):
        """Convert normalized L [0,1] to L* [0, 100] as expected by the model."""
        return l_channel * 100.0

    def colorize_frame(self, l_channel: np.ndarray) -> np.ndarray:
        """Take L channel (HxW float32 0-1), return RGB (HxWx3 uint8)."""
        self._load()
        H, W = l_channel.shape
        img_l = self._prepare_input(l_channel)
        img_l = torch.from_numpy(img_l).float().unsqueeze(0).unsqueeze(0)
        img_l = img_l.to(self._device)
        if self._fp16:
            img_l = img_l.half()
        with torch.no_grad():
            pred_ab = self._model(img_l)
        pred_ab = pred_ab.squeeze(0).cpu().numpy().transpose(1, 2, 0)
        rgb = luma_to_rgb(l_channel, pred_ab)
        return rgb

    def colorize_batch(self, l_batch: np.ndarray) -> np.ndarray:
        """Take batch of L channels (BxHxW float32 0-1), return RGB (BxHxWx3 uint8)."""
        self._load()
        B, H, W = l_batch.shape
        img_l = self._prepare_input(l_batch)
        img_l = torch.from_numpy(img_l).float().unsqueeze(1)
        img_l = img_l.to(self._device)
        if self._fp16:
            img_l = img_l.half()
        with torch.no_grad():
            pred_ab = self._model(img_l)
        pred_ab = pred_ab.cpu().numpy().transpose(0, 2, 3, 1)
        results = []
        for i in range(B):
            rgb = luma_to_rgb(l_batch[i], pred_ab[i])
            results.append(rgb)
        return np.stack(results, axis=0)

    def name(self) -> str:
        return "eccv16"

    def supports_batch(self) -> bool:
        return True

    def supported_filters(self) -> dict:
        return {"saturation": True, "fp16": True, "batch_size": True}
