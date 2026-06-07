"""BigColor — BigGAN-based colorization (CVPR 2022).

Self-contained inference implementation of:
  BigColor: Colorization using a Generative Color Prior for Natural Images
  Kim et al., ECCV 2022

Requires: timm + scikit-image (optional: for automatic class prediction)
"""
from __future__ import annotations
import os, re
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import Parameter as P
import numpy as np
from colorizers.base import Colorizer
from colorizers.utils import luma_to_rgb

# ---------------------------------------------------------------------------
#  Model weight URLs
# ---------------------------------------------------------------------------

MODEL_URLS = {
    "checkpoint": "https://drive.google.com/drive/folders/1nLzgE5WJnxp5WF1dkpa1ts6bZ6tVwtep",
}
MODEL_FILES = {
    "checkpoint": "EG_EMA_011.ckpt",
}

# ---------------------------------------------------------------------------
#  BigGAN Generator — self-contained inference version
# ---------------------------------------------------------------------------

def G_arch(ch=64, attention='64'):
    arch = {}
    arch[256] = {
        'in_channels': [ch * item for item in [16, 16, 8, 8, 4, 2]],
        'out_channels': [ch * item for item in [16, 8, 8, 4, 2, 1]],
        'upsample': [True] * 6,
        'resolution': [8, 16, 32, 64, 128, 256],
        'attention': {2**i: (2**i in [int(item) for item in attention.split('_')]) for i in range(3, 9)}
    }
    arch[128] = {
        'in_channels': [ch * item for item in [16, 16, 8, 4, 2]],
        'out_channels': [ch * item for item in [16, 8, 4, 2, 1]],
        'upsample': [True] * 5,
        'resolution': [8, 16, 32, 64, 128],
        'attention': {2**i: (2**i in [int(item) for item in attention.split('_')]) for i in range(3, 8)}
    }
    return arch

# ---- Spectral Normalization helpers ----

def _l2normalize(v, eps=1e-12):
    return v / (torch.norm(v) + eps)

def _power_iteration(W, u_, num_itrs=1, eps=1e-12):
    svs = []
    for u in u_:
        v = _l2normalize(torch.matmul(u, W), eps)
        u = _l2normalize(torch.matmul(v, W.t()), eps)
        sv = torch.sum(u * torch.matmul(v, W.t()))
        svs.append(sv)
    return svs

class _SNConv2d(nn.Conv2d):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=0,
                 dilation=1, groups=1, bias=True, num_svs=1, num_itrs=1, eps=1e-12):
        super().__init__(in_channels, out_channels, kernel_size, stride, padding, dilation, groups, bias)
        self.num_svs = num_svs
        self.num_itrs = num_itrs
        self.eps = eps
        for i in range(num_svs):
            self.register_buffer('u%d' % i, torch.randn(1, out_channels))

    def _W(self):
        W_mat = self.weight.view(self.weight.size(0), -1)
        u_ = [getattr(self, 'u%d' % i) for i in range(self.num_svs)]
        for _ in range(self.num_itrs):
            svs = _power_iteration(W_mat, u_, eps=self.eps)
        return self.weight / svs[0].clamp(min=1e-12)

    def forward(self, x):
        return F.conv2d(x, self._W(), self.bias, self.stride, self.padding, self.dilation, self.groups)

class _SNLinear(nn.Linear):
    def __init__(self, in_features, out_features, bias=True, num_svs=1, num_itrs=1, eps=1e-12):
        super().__init__(in_features, out_features, bias)
        self.num_svs = num_svs
        self.num_itrs = num_itrs
        self.eps = eps
        for i in range(num_svs):
            self.register_buffer('u%d' % i, torch.randn(1, out_features))

    def _W(self):
        W_mat = self.weight.view(self.weight.size(0), -1)
        u_ = [getattr(self, 'u%d' % i) for i in range(self.num_svs)]
        for _ in range(self.num_itrs):
            svs = _power_iteration(W_mat, u_, eps=self.eps)
        return self.weight / svs[0].clamp(min=1e-12)

    def forward(self, x):
        return F.linear(x, self._W(), self.bias)

# ---- Attention ----

class _Attention(nn.Module):
    def __init__(self, ch, which_conv):
        super().__init__()
        self.ch = ch
        self.which_conv = which_conv
        self.theta = which_conv(ch, ch // 8, kernel_size=1, padding=0, bias=False)
        self.phi   = which_conv(ch, ch // 8, kernel_size=1, padding=0, bias=False)
        self.g     = which_conv(ch, ch // 2, kernel_size=1, padding=0, bias=False)
        self.o     = which_conv(ch // 2, ch, kernel_size=1, padding=0, bias=False)
        self.gamma = P(torch.tensor(0.), requires_grad=True)

    def forward(self, x, y=None):
        theta = self.theta(x)
        phi   = F.max_pool2d(self.phi(x), 2)
        g     = F.max_pool2d(self.g(x), 2)
        B, C, H, W = x.shape
        theta = theta.view(B, self.ch // 8, H * W)
        phi   = phi.view(B, self.ch // 8, H * W // 4)
        g     = g.view(B, self.ch // 2, H * W // 4)
        beta = F.softmax(torch.bmm(theta.transpose(1, 2), phi), -1)
        o = self.o(torch.bmm(g, beta.transpose(1, 2)).view(B, self.ch // 2, H, W))
        return self.gamma * o + x

# ---- Batch Normalization ----

class _bn(nn.Module):
    def __init__(self, output_size, eps=1e-5, momentum=0.1):
        super().__init__()
        self.gain = P(torch.ones(output_size), requires_grad=True)
        self.bias = P(torch.zeros(output_size), requires_grad=True)
        self.eps = eps
        self.momentum = momentum
        self.register_buffer('stored_mean', torch.zeros(output_size))
        self.register_buffer('stored_var', torch.ones(output_size))

    def forward(self, x, y=None):
        return F.batch_norm(x, self.stored_mean, self.stored_var, self.gain, self.bias,
                            self.training, self.momentum, self.eps)

class _ccbn(nn.Module):
    """Class-conditional BatchNorm."""
    def __init__(self, output_size, input_size, which_linear, eps=1e-5, momentum=0.1, norm_style='bn'):
        super().__init__()
        self.gain = which_linear(input_size, output_size)
        self.bias = which_linear(input_size, output_size)
        self.eps = eps
        self.momentum = momentum
        self.norm_style = norm_style
        self.register_buffer('stored_mean', torch.zeros(output_size))
        self.register_buffer('stored_var', torch.ones(output_size))

    def forward(self, x, y):
        gain = (1 + self.gain(y)).view(y.size(0), -1, 1, 1)
        bias = self.bias(y).view(y.size(0), -1, 1, 1)
        out = F.batch_norm(x, self.stored_mean, self.stored_var, None, None,
                           self.training, 0.1, self.eps)
        return out * gain + bias

class _identity(nn.Module):
    def forward(self, x):
        return x

# ---- G Block ----

class _GBlock(nn.Module):
    def __init__(self, in_channels, out_channels, which_conv, which_bn,
                 activation=None, upsample=None):
        super().__init__()
        self.in_channels, self.out_channels = in_channels, out_channels
        self.which_conv, self.which_bn = which_conv, which_bn
        self.activation = activation
        self.upsample = upsample
        self.conv1 = which_conv(in_channels, out_channels)
        self.conv2 = which_conv(out_channels, out_channels)
        self.learnable_sc = in_channels != out_channels or upsample is not None
        if self.learnable_sc:
            self.conv_sc = which_conv(in_channels, out_channels, kernel_size=1, padding=0)
        self.bn1 = which_bn(in_channels)
        self.bn2 = which_bn(out_channels)

    def forward(self, x, y, use_in=False):
        h = self.bn1(x, y)
        h = self.activation(h)
        if self.upsample:
            h = self.upsample(h)
            x = self.upsample(x)
        h = self.conv1(h)
        h = self.bn2(h, y)
        h = self.activation(h)
        h = self.conv2(h)
        if self.learnable_sc:
            x = self.conv_sc(x)
        return h + x

# ---- Generator ----

class _Generator(nn.Module):
    """BigGAN Generator (inference-only, adapted for BigColor)."""
    def __init__(self, G_ch=64, dim_z=128, bottom_width=4, resolution=256,
                 G_attn='64', n_classes=1000, G_shared=True, shared_dim=0,
                 hier=False, G_activation=nn.ReLU(inplace=True),
                 G_param='SN', norm_style='bn', num_G_SVs=1, num_G_SV_itrs=1,
                 SN_eps=1e-12, BN_eps=1e-5, **kwargs):
        super().__init__()
        self.ch = G_ch
        self.dim_z = dim_z
        self.bottom_width = bottom_width
        self.resolution = resolution
        self.n_classes = n_classes
        self.G_shared = G_shared
        self.shared_dim = shared_dim if shared_dim > 0 else dim_z
        self.hier = hier
        self.activation = G_activation
        self.G_param = G_param
        self.norm_style = norm_style
        self.arch = G_arch(self.ch, G_attn)[resolution]

        if self.hier:
            self.num_slots = len(self.arch['in_channels']) + 1
            self.z_chunk_size = self.dim_z // self.num_slots
            self.dim_z = self.z_chunk_size * self.num_slots
        else:
            self.num_slots = 1
            self.z_chunk_size = 0

        wc = functools.partial(_SNConv2d, kernel_size=3, padding=1,
                                num_svs=num_G_SVs, num_itrs=num_G_SV_itrs,
                                eps=SN_eps)
        wl = functools.partial(_SNLinear, num_svs=num_G_SVs, num_itrs=num_G_SV_itrs,
                                eps=SN_eps)
        we = nn.Embedding

        bn_linear = functools.partial(wl, bias=False) if self.G_shared else we
        self.which_bn = functools.partial(
            _ccbn, which_linear=bn_linear,
            input_size=(self.shared_dim + self.z_chunk_size if self.G_shared else self.n_classes),
            norm_style=self.norm_style, eps=BN_eps)

        self.shared = we(n_classes, self.shared_dim) if G_shared else _identity()
        self.linear = wl(self.dim_z // self.num_slots,
                         self.arch['in_channels'][0] * (self.bottom_width ** 2))

        self.blocks = nn.ModuleList()
        for idx in range(len(self.arch['out_channels'])):
            block_list = nn.ModuleList([
                _GBlock(
                    in_channels=self.arch['in_channels'][idx],
                    out_channels=self.arch['out_channels'][idx],
                    which_conv=wc,
                    which_bn=self.which_bn,
                    activation=self.activation,
                    upsample=(functools.partial(F.interpolate, scale_factor=2)
                              if self.arch['upsample'][idx] else None))
            ])
            if self.arch['attention'][self.arch['resolution'][idx]]:
                block_list.append(_Attention(self.arch['out_channels'][idx], wc))
            self.blocks.append(block_list)

        self.output_layer = nn.Sequential(
            _bn(self.arch['out_channels'][-1], eps=BN_eps),
            self.activation,
            wc(self.arch['out_channels'][-1], 3))

    def forward(self, z, y):
        if self.hier:
            zs = torch.split(z, self.z_chunk_size, 1)
            z = zs[0]
            ys = [torch.cat([y, item], 1) for item in zs[1:]]
        else:
            ys = [y] * len(self.blocks)

        h = self.linear(z)
        h = h.view(h.size(0), -1, self.bottom_width, self.bottom_width)

        for blocklist in self.blocks:
            for block in blocklist:
                h = block(h, ys[0])
        return torch.tanh(self.output_layer(h))

    def forward_from(self, z, y, num_layer, h):
        if num_layer == 0:
            return self.forward(h, y)
        if self.hier:
            zs = torch.split(z, self.z_chunk_size, 1)
            z = zs[0]
            ys = [torch.cat([y, item], 1) for item in zs[1:]]
        else:
            ys = [y] * len(self.blocks)

        for idx, blocklist in enumerate(self.blocks):
            if idx < num_layer:
                continue
            for block in blocklist:
                h = block(h, ys[idx])
        return torch.tanh(self.output_layer(h))

    def forward_to(self, z, y, num_layer):
        if self.hier:
            zs = torch.split(z, self.z_chunk_size, 1)
            z = zs[0]
            ys = [torch.cat([y, item], 1) for item in zs[1:]]
        else:
            ys = [y] * len(self.blocks)

        h = self.linear(z)
        h = h.view(h.size(0), -1, self.bottom_width, self.bottom_width)
        for idx, blocklist in enumerate(self.blocks):
            if idx == num_layer:
                return h
            for block in blocklist:
                h = block(h, ys[idx])
        return torch.tanh(self.output_layer(h))

import functools

# ---------------------------------------------------------------------------
#  Encoder  —  EncoderF_Res (dim_f=16)
# ---------------------------------------------------------------------------

class _ClassConditionNorm(nn.Module):
    def __init__(self, output_size, input_size, which_linear=None, eps=1e-5, norm_style='bn'):
        super().__init__()
        if which_linear is None:
            which_linear = functools.partial(nn.Linear, bias=False)
        self.gain = which_linear(input_size, output_size)
        self.bias = which_linear(input_size, output_size)
        self.eps = eps
        self.norm_style = norm_style
        self.register_buffer('stored_mean', torch.zeros(output_size))
        self.register_buffer('stored_var', torch.ones(output_size))

    def forward(self, x, y):
        gain = (1 + self.gain(y)).view(y.size(0), -1, 1, 1)
        bias = self.bias(y).view(y.size(0), -1, 1, 1)
        out = F.batch_norm(x, self.stored_mean, self.stored_var, None, None,
                           self.training, 0.1, self.eps)
        return out * gain + bias


class _ResConvBlock(nn.Module):
    def __init__(self, ch_in, ch_out, is_down=False, activation='relu',
                 norm='adabatch', use_res=True, ch_c=128, dropout=0.2):
        super().__init__()
        self.is_down = is_down
        self.use_res = use_res
        if self.use_res:
            self.conv = nn.Conv2d(ch_in, ch_out, kernel_size=1, stride=1, padding=0)
        self.conv_1 = nn.Conv2d(ch_in, ch_out, kernel_size=3, stride=1, padding=1)
        self.conv_2 = nn.Conv2d(ch_out, ch_out, kernel_size=3, stride=1, padding=1)

        if norm == 'adabatch':
            self.norm1 = _ClassConditionNorm(ch_in, ch_c, norm_style='bn')
            self.norm2 = _ClassConditionNorm(ch_out, ch_c, norm_style='bn')
        elif norm == 'batch':
            self.norm1 = nn.BatchNorm2d(ch_in)
            self.norm2 = nn.BatchNorm2d(ch_out)
        elif norm == 'id':
            self.norm1 = nn.Identity()
            self.norm2 = nn.Identity()
        else:
            raise ValueError(f'Unknown norm: {norm}')

        if activation == 'relu':
            self.act = nn.ReLU(inplace=True)
        elif activation == 'lrelu':
            self.act = nn.LeakyReLU(0.2, inplace=True)
        else:
            raise ValueError(f'Unknown activation: {activation}')

        self.pool = nn.AvgPool2d(2) if is_down else None
        self.dropout = nn.Dropout(dropout) if dropout is not None else None

    def forward(self, x, c=None):
        x_ = x
        x_ = self.norm1(x_, c) if c is not None else self.norm1(x_)
        x_ = self.act(x_)
        if self.is_down:
            x_ = self.pool(x_)
        x_ = self.conv_1(x_)
        x_ = self.norm2(x_, c) if c is not None else self.norm2(x_)
        x_ = self.act(x_)
        x_ = self.conv_2(x_)

        if self.use_res:
            x_res = x
            if self.is_down:
                x_res = self.pool(x_res)
            x_res = self.conv(x_res)
            x = x_res + x_
        else:
            x = x_

        if self.dropout is not None:
            x = self.dropout(x)
        return x


class _EncoderF_Res(nn.Module):
    """EncoderF_Res with dim_f=16: outputs 768x16x16 feature map."""
    def __init__(self, ch_in=1, ch_unit=96, norm='adabatch', activation='relu',
                 use_att=True, use_res=True):
        super().__init__()
        self.res1 = _ResConvBlock(ch_in, ch_unit * 1, is_down=False, activation=activation, norm=norm, use_res=use_res)
        self.res2 = _ResConvBlock(ch_unit * 1, ch_unit * 2, is_down=True, activation=activation, norm=norm, use_res=use_res)
        self.res3 = _ResConvBlock(ch_unit * 2, ch_unit * 4, is_down=True, activation=activation, norm=norm, use_res=use_res)
        self.res4 = _ResConvBlock(ch_unit * 4, ch_unit * 8, is_down=True, activation=activation, norm=norm, use_res=use_res, dropout=None)
        self.res5 = _ResConvBlock(ch_unit * 8, ch_unit * 8, is_down=True, activation=activation, norm=norm, use_res=use_res, dropout=None)

        self.use_att = use_att
        if use_att:
            conv4att = functools.partial(_SNConv2d, kernel_size=3, padding=1, num_svs=1, num_itrs=1, eps=1e-6)
            self.att = _Attention(384, conv4att)

    def forward(self, x, c=None):
        x = self.res1(x, c)
        x = self.res2(x, c)
        x = self.res3(x, c)
        if self.use_att:
            x = self.att(x)
        x = self.res4(x, c)
        x = self.res5(x, c)
        return x


# ---------------------------------------------------------------------------
#  Colorizer (Encoder + Generator)
# ---------------------------------------------------------------------------

class _Colorizer(nn.Module):
    """BigColor Colorizer: Encoder -> Generator mid-layer injection."""

    def __init__(self, config: dict, norm_type='adabatch',
                 id_mid_layer=2, activation='relu', use_attention=True,
                 use_res=True, dim_f=16):
        super().__init__()
        self.id_mid_layer = id_mid_layer
        self.E = _EncoderF_Res(norm=norm_type, activation=activation,
                                use_att=use_attention, use_res=use_res)
        self.G = _Generator(**config)

    def forward(self, x_gray, c, z):
        """ x_gray: (B,1,H,W) in [0,1]
            c: (B,) LongTensor class labels
            z: (B, dim_z) noise
        """
        c_emb = self.G.shared(c)
        f = self.E(x_gray, c_emb)
        return self.G.forward_from(z, c_emb, self.id_mid_layer, f)


# ---------------------------------------------------------------------------
#  BigColorColorizer  —  implements Colorizer ABC
# ---------------------------------------------------------------------------

BIGCOLOR_CONFIG = {
    'G_ch': 96, 'dim_z': 119, 'bottom_width': 4, 'resolution': 256,
    'G_attn': '64', 'n_classes': 1000, 'G_shared': True, 'shared_dim': 128,
    'hier': False, 'norm_style': 'bn', 'num_G_SVs': 1, 'num_G_SV_itrs': 1,
    'SN_eps': 1e-12, 'BN_eps': 1e-5,
}


class BigColorColorizer(Colorizer):
    """BigColor colorizer wrapper.

    Takes L channel (HxW float32 0-1), outputs RGB (HxWx3 uint8).

    Requires:
      - BigColor checkpoint (EG_EMA_*.ckpt) containing Encoder+Generator weights
      - Optional: timm for automatic class prediction
    """

    def __init__(self, weight_path: str, device: str = 'cuda:0',
                 fp16: bool = True, input_size: int = 512,
                 class_id: int = 0):
        self._weight_path = weight_path
        self._dev = torch.device(device if torch.cuda.is_available() and 'cuda' in device else 'cpu')
        self._fp16 = fp16 and self._dev.type == 'cuda'
        self._input_size = input_size
        self._class_id = class_id
        self._model = None
        self._dim_z = BIGCOLOR_CONFIG['dim_z']

    def _load(self):
        if self._model is not None:
            return
        if not os.path.isfile(self._weight_path):
            raise FileNotFoundError(
                f"BigColor weights not found at: {self._weight_path}\n"
                f"Download from: {MODEL_URLS['checkpoint']}"
            )
        model = _Colorizer(BIGCOLOR_CONFIG, norm_type='adabatch',
                           id_mid_layer=2, activation='relu',
                           use_attention=True, use_res=True)
        sd = torch.load(self._weight_path, map_location='cpu', weights_only=False)
        if 'model' in sd:
            sd = sd['model']
        elif 'state_dict' in sd:
            sd = sd['state_dict']
        errs = model.load_state_dict(sd, strict=False)
        if errs[0]:
            print(f'BigColor missing keys ({len(errs[0])}):', list(errs[0])[:10])
        if errs[1]:
            print(f'BigColor unexpected keys ({len(errs[1])}):', list(errs[1])[:10])
        model.eval()
        model.to(self._dev)
        if self._fp16:
            model = model.half()
        self._model = model

    def _predict_class(self, gray_rgb: np.ndarray) -> int:
        """Use timm classifier to predict ImageNet class from grayscale image."""
        try:
            import timm
            from torchvision import transforms
        except ImportError:
            return self._class_id
        try:
            classifier = timm.create_model('tf_efficientnet_l2_ns_475',
                                            pretrained=True, num_classes=1000)
            classifier = classifier.to(self._dev).eval()
            size_cls = 475
            t = torch.from_numpy(gray_rgb.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0
            t = F.interpolate(t, (size_cls, size_cls), mode='bilinear', align_corners=False)
            t = t.to(self._dev)
            with torch.no_grad():
                logits = classifier(t)
            pred = logits.argmax(1).item()
            return pred
        except Exception:
            return self._class_id

    def colorize_frame(self, l_channel: np.ndarray) -> np.ndarray:
        """Take L channel (HxW float32 0-1), return RGB (HxWx3 uint8)."""
        self._load()
        import cv2
        H, W = l_channel.shape
        gray_3ch = np.stack([l_channel] * 3, axis=-1).astype(np.float32)

        klass = self._class_id
        h_in, w_in = gray_3ch.shape[:2]
        short = min(h_in, w_in)
        scale = self._input_size / short
        new_w, new_h = int(w_in * scale), int(h_in * scale)
        gray_resized = cv2.resize(gray_3ch, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        t = torch.from_numpy(gray_resized.transpose(2, 0, 1)).float().unsqueeze(0).to(self._dev)
        if self._fp16:
            t = t.half()

        c = torch.LongTensor([klass]).to(self._dev)
        z = torch.randn(1, self._dim_z, device=self._dev) * 0.8

        with torch.no_grad():
            output = self._model(t, c, z)
            output = (output + 1.0) / 2.0

        out_rgb = output.squeeze(0).cpu().float().numpy().transpose(1, 2, 0)
        out_rgb = np.clip(out_rgb, 0, 1)
        out_rgb = (out_rgb * 255).astype(np.uint8)
        out_rgb = cv2.resize(out_rgb, (W, H), interpolation=cv2.INTER_LINEAR)

        ab = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2LAB)[:, :, 1:]
        lab = np.concatenate([(l_channel * 100.0)[:, :, np.newaxis], ab], axis=-1)
        result = cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_LAB2RGB)
        return np.clip(result * 255, 0, 255).astype(np.uint8)

    def colorize_batch(self, l_batch: np.ndarray) -> np.ndarray:
        return np.stack([self.colorize_frame(l_batch[i]) for i in range(l_batch.shape[0])])

    def name(self) -> str:
        return 'bigcolor'

    def supports_batch(self) -> bool:
        return False

    def supported_filters(self) -> dict:
        return {'input_size': True, 'class_id': True}
