import math
import os
from collections import OrderedDict
from enum import Enum
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from colorizers.base import Colorizer
from colorizers.utils import luma_to_rgb


# ── timm-free helpers ──────────────────────────────────────────

def trunc_normal_(tensor, mean=0.0, std=1.0, a=-2.0, b=2.0):
    if hasattr(torch.nn.init, "trunc_normal_"):
        return torch.nn.init.trunc_normal_(tensor, mean=mean, std=std, a=a, b=b)

    def norm_cdf(x):
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    with torch.no_grad():
        l_ = norm_cdf((a - mean) / std)
        u_ = norm_cdf((b - mean) / std)
        tensor.uniform_(2 * l_ - 1, 2 * u_ - 1)
        tensor.erfinv_()
        tensor.mul_(std * math.sqrt(2.0))
        tensor.add_(mean)
        tensor.clamp_(min=a, max=b)
        return tensor


class DropPath(nn.Module):
    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = float(drop_prob)

    def forward(self, x):
        if self.drop_prob == 0.0 or not self.training:
            return x
        keep_prob = 1.0 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()
        return x.div(keep_prob) * random_tensor


# ── ConvNeXt ──────────────────────────────────────────────────

class LayerNorm(nn.Module):
    def __init__(self, normalized_shape, eps=1e-6, data_format="channels_last"):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.eps = eps
        self.data_format = data_format
        self.normalized_shape = (normalized_shape,)

    def forward(self, x):
        if self.data_format == "channels_last":
            return F.layer_norm(x, self.normalized_shape, self.weight, self.bias, self.eps)
        u = x.mean(1, keepdim=True)
        s = (x - u).pow(2).mean(1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.eps)
        x = self.weight[:, None, None] * x + self.bias[:, None, None]
        return x


class ConvNeXtBlock(nn.Module):
    def __init__(self, dim, drop_path=0.0, layer_scale_init_value=1e-6):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.norm = LayerNorm(dim, eps=1e-6)
        self.pwconv1 = nn.Linear(dim, 4 * dim)
        self.act = nn.GELU()
        self.pwconv2 = nn.Linear(4 * dim, dim)
        self.gamma = nn.Parameter(
            layer_scale_init_value * torch.ones(dim),
            requires_grad=True,
        ) if layer_scale_init_value > 0 else None
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

    def forward(self, x):
        inp = x
        x = self.dwconv(x)
        x = x.permute(0, 2, 3, 1)
        x = self.norm(x)
        x = self.pwconv1(x)
        x = self.act(x)
        x = self.pwconv2(x)
        if self.gamma is not None:
            x = self.gamma * x
        x = x.permute(0, 3, 1, 2)
        return inp + self.drop_path(x)


class ConvNeXt(nn.Module):
    def __init__(
        self,
        in_chans=3,
        depths=(3, 3, 9, 3),
        dims=(96, 192, 384, 768),
        drop_path_rate=0.0,
        layer_scale_init_value=1e-6,
    ):
        super().__init__()

        self.downsample_layers = nn.ModuleList()
        stem = nn.Sequential(
            nn.Conv2d(in_chans, dims[0], kernel_size=4, stride=4),
            LayerNorm(dims[0], eps=1e-6, data_format="channels_first"),
        )
        self.downsample_layers.append(stem)
        for i in range(3):
            dl = nn.Sequential(
                LayerNorm(dims[i], eps=1e-6, data_format="channels_first"),
                nn.Conv2d(dims[i], dims[i + 1], kernel_size=2, stride=2),
            )
            self.downsample_layers.append(dl)

        self.stages = nn.ModuleList()
        dp_rates = [x.item() for x in torch.linspace(0, drop_path_rate, sum(depths))]
        cur = 0
        for i in range(4):
            stage = nn.Sequential(
                *[ConvNeXtBlock(dim=dims[i], drop_path=dp_rates[cur + j], layer_scale_init_value=layer_scale_init_value) for j in range(depths[i])]
            )
            self.stages.append(stage)
            cur += depths[i]

        for i in range(4):
            layer = LayerNorm(dims[i], eps=1e-6, data_format="channels_first")
            self.add_module(f"norm{i}", layer)

        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, (nn.Conv2d, nn.Linear)):
            trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        for i in range(4):
            x = self.downsample_layers[i](x)
            x = self.stages[i](x)
            norm_layer = getattr(self, f"norm{i}")
            norm_layer(x)
        return x


# ── UNet helpers ──────────────────────────────────────────────

NormType = Enum("NormType", "Batch BatchZero Weight Spectral")


class Hook:
    feature = None

    def __init__(self, module):
        self.hook = module.register_forward_hook(self.hook_fn)

    def hook_fn(self, module, input, output):
        if isinstance(output, torch.Tensor):
            self.feature = output
        elif isinstance(output, OrderedDict):
            self.feature = output["out"]

    def remove(self):
        self.hook.remove()


class SelfAttention(nn.Module):
    def __init__(self, n_channels: int):
        super().__init__()
        self.query = self._conv1d(n_channels, n_channels // 8)
        self.key = self._conv1d(n_channels, n_channels // 8)
        self.value = self._conv1d(n_channels, n_channels)
        self.gamma = nn.Parameter(torch.tensor([0.0]))

    @staticmethod
    def _conv1d(ni, no):
        conv = nn.Conv1d(ni, no, 1, bias=False)
        nn.init.kaiming_normal_(conv.weight)
        return nn.utils.spectral_norm(conv)

    def forward(self, x):
        size = x.size()
        x = x.view(*size[:2], -1)
        f, g, h = self.query(x), self.key(x), self.value(x)
        beta = F.softmax(torch.bmm(f.permute(0, 2, 1).contiguous(), g), dim=1)
        o = self.gamma * torch.bmm(h, beta) + x
        return o.view(*size).contiguous()


def batchnorm_2d(nf, norm_type=NormType.Batch):
    bn = nn.BatchNorm2d(nf)
    with torch.no_grad():
        bn.bias.fill_(1e-3)
        bn.weight.fill_(0.0 if norm_type == NormType.BatchZero else 1.0)
    return bn


def init_default(m, func=nn.init.kaiming_normal_):
    if func and hasattr(m, "weight"):
        func(m.weight)
    if hasattr(m, "bias") and hasattr(m.bias, "data"):
        m.bias.data.fill_(0.0)
    return m


def icnr(x, scale=2, init=nn.init.kaiming_normal_):
    ni, nf, h, w = x.shape
    ni2 = int(ni / (scale**2))
    k = init(torch.zeros([ni2, nf, h, w])).transpose(0, 1)
    k = k.contiguous().view(ni2, nf, -1)
    k = k.repeat(1, 1, scale**2)
    k = k.contiguous().view([nf, ni, h, w]).transpose(0, 1)
    x.data.copy_(k)


def custom_conv_layer(
    ni,
    nf,
    ks=3,
    stride=1,
    padding=None,
    bias=None,
    norm_type=NormType.Batch,
    use_activ=True,
    transpose=False,
    init=nn.init.kaiming_normal_,
    self_attention=False,
    extra_bn=False,
):
    if padding is None:
        padding = (ks - 1) // 2 if not transpose else 0
    bn = norm_type in (NormType.Batch, NormType.BatchZero) or extra_bn
    if bias is None:
        bias = not bn
    conv_func = nn.ConvTranspose2d if transpose else nn.Conv2d
    conv = init_default(conv_func(ni, nf, kernel_size=ks, bias=bias, stride=stride, padding=padding), init)
    if norm_type == NormType.Weight:
        conv = nn.utils.weight_norm(conv)
    elif norm_type == NormType.Spectral:
        conv = nn.utils.spectral_norm(conv)
    layers = [conv]
    if use_activ:
        layers.append(nn.ReLU(True))
    if bn:
        layers.append(nn.BatchNorm2d(nf))
    if self_attention:
        layers.append(SelfAttention(nf))
    return nn.Sequential(*layers)


class CustomPixelShuffle_ICNR(nn.Module):
    def __init__(self, ni, nf=None, scale=2, blur=True, norm_type=NormType.Spectral, extra_bn=False):
        super().__init__()
        if nf is None:
            nf = ni
        self.conv = custom_conv_layer(ni, nf * (scale**2), ks=1, use_activ=False, norm_type=norm_type, extra_bn=extra_bn)
        icnr(self.conv[0].weight)
        self.shuf = nn.PixelShuffle(scale)
        self.do_blur = blur
        self.pad = nn.ReplicationPad2d((1, 0, 1, 0))
        self.blur = nn.AvgPool2d(2, stride=1)
        self.relu = nn.ReLU(True)

    def forward(self, x):
        x = self.shuf(self.relu(self.conv(x)))
        return self.blur(self.pad(x)) if self.do_blur else x


class UnetBlockWide(nn.Module):
    def __init__(self, up_in_c, x_in_c, n_out, hook, blur=False, self_attention=False, norm_type=NormType.Spectral):
        super().__init__()
        self.hook = hook
        self.shuf = CustomPixelShuffle_ICNR(up_in_c, n_out, blur=blur, norm_type=norm_type, extra_bn=True)
        self.bn = batchnorm_2d(x_in_c)
        self.conv = custom_conv_layer(n_out + x_in_c, n_out, norm_type=norm_type, self_attention=self_attention, extra_bn=True)
        self.relu = nn.ReLU()

    def forward(self, up_in):
        s = self.hook.feature
        up_out = self.shuf(up_in)
        cat_x = self.relu(torch.cat([up_out, self.bn(s)], dim=1))
        return self.conv(cat_x)


# ── Transformer utilities (DETR-style) ───────────────────────

class SelfAttentionLayer(nn.Module):
    def __init__(self, d_model, nhead, dropout=0.0, activation="relu", normalize_before=False):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = _get_activation_fn(activation)
        self.normalize_before = normalize_before
        self._reset_parameters()

    def _reset_parameters(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    @staticmethod
    def with_pos_embed(tensor, pos):
        return tensor if pos is None else tensor + pos

    def forward(self, tgt, tgt_mask=None, tgt_key_padding_mask=None, query_pos=None):
        q = k = self.with_pos_embed(tgt, query_pos)
        tgt2 = self.self_attn(q, k, value=tgt, attn_mask=tgt_mask, key_padding_mask=tgt_key_padding_mask)[0]
        tgt = tgt + self.dropout(tgt2)
        tgt = self.norm(tgt)
        return tgt


class CrossAttentionLayer(nn.Module):
    def __init__(self, d_model, nhead, dropout=0.0, activation="relu", normalize_before=False):
        super().__init__()
        self.multihead_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = _get_activation_fn(activation)
        self.normalize_before = normalize_before
        self._reset_parameters()

    def _reset_parameters(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    @staticmethod
    def with_pos_embed(tensor, pos):
        return tensor if pos is None else tensor + pos

    def forward(self, tgt, memory, memory_mask=None, memory_key_padding_mask=None, pos=None, query_pos=None):
        tgt2 = self.multihead_attn(
            query=self.with_pos_embed(tgt, query_pos),
            key=self.with_pos_embed(memory, pos),
            value=memory,
            attn_mask=memory_mask,
            key_padding_mask=memory_key_padding_mask,
        )[0]
        tgt = tgt + self.dropout(tgt2)
        tgt = self.norm(tgt)
        return tgt


class FFNLayer(nn.Module):
    def __init__(self, d_model, dim_feedforward=2048, dropout=0.0, activation="relu", normalize_before=False):
        super().__init__()
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        self.norm = nn.LayerNorm(d_model)
        self.activation = _get_activation_fn(activation)
        self.normalize_before = normalize_before
        self._reset_parameters()

    def _reset_parameters(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(self, tgt):
        tgt2 = self.linear2(self.dropout(self.activation(self.linear1(tgt))))
        tgt = tgt + self.dropout(tgt2)
        tgt = self.norm(tgt)
        return tgt


def _get_activation_fn(activation):
    if activation == "relu":
        return F.relu
    if activation == "gelu":
        return F.gelu
    raise RuntimeError(f"activation should be relu/gelu, not {activation}")


class MLP(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers):
        super().__init__()
        self.num_layers = num_layers
        h = [hidden_dim] * (num_layers - 1)
        self.layers = nn.ModuleList(nn.Linear(n, k) for n, k in zip([input_dim] + h, h + [output_dim]))

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = F.relu(layer(x)) if i < self.num_layers - 1 else layer(x)
        return x


# ── Position encoding ────────────────────────────────────────

class PositionEmbeddingSine(nn.Module):
    def __init__(self, num_pos_feats=64, temperature=10000, normalize=False, scale=None):
        super().__init__()
        self.num_pos_feats = num_pos_feats
        self.temperature = temperature
        self.normalize = normalize
        if scale is None:
            scale = 2 * math.pi
        self.scale = scale

    def forward(self, x, mask=None):
        if mask is None:
            mask = torch.zeros(x.size(0), x.size(2), x.size(3), device=x.device, dtype=torch.bool)
        not_mask = ~mask
        y_embed = not_mask.cumsum(1, dtype=torch.float32)
        x_embed = not_mask.cumsum(2, dtype=torch.float32)
        if self.normalize:
            eps = 1e-6
            y_embed = y_embed / (y_embed[:, -1:, :] + eps) * self.scale
            x_embed = x_embed / (x_embed[:, :, -1:] + eps) * self.scale

        dim_t = torch.arange(self.num_pos_feats, dtype=torch.float32, device=x.device)
        dim_t = self.temperature ** (2 * (dim_t // 2) / self.num_pos_feats)

        pos_x = x_embed[:, :, :, None] / dim_t
        pos_y = y_embed[:, :, :, None] / dim_t
        pos_x = torch.stack((pos_x[:, :, :, 0::2].sin(), pos_x[:, :, :, 1::2].cos()), dim=4).flatten(3)
        pos_y = torch.stack((pos_y[:, :, :, 0::2].sin(), pos_y[:, :, :, 1::2].cos()), dim=4).flatten(3)
        pos = torch.cat((pos_y, pos_x), dim=3).permute(0, 3, 1, 2)
        return pos


# ── Image Encoder (ConvNeXt wrapper) ─────────────────────────

class ImageEncoder(nn.Module):
    def __init__(self, encoder_name="convnext-l"):
        super().__init__()
        assert encoder_name in ("convnext-t", "convnext-l")
        if encoder_name == "convnext-t":
            self.arch = ConvNeXt(depths=[3, 3, 9, 3], dims=[96, 192, 384, 768])
        else:
            self.arch = ConvNeXt(depths=[3, 3, 27, 3], dims=[192, 384, 768, 1536])
        self.hook_names = ["norm0", "norm1", "norm2", "norm3"]
        self.hooks = self._setup_hooks()

    def _setup_hooks(self):
        return [Hook(self.arch._modules[name]) for name in self.hook_names]

    def forward(self, x):
        return self.arch(x)


# ── Dual Decoder ──────────────────────────────────────────────

class DuelDecoder(nn.Module):
    def __init__(self, hooks, nf=512, blur=True, last_norm=NormType.Spectral, num_queries=256, num_scales=3, dec_layers=9):
        super().__init__()
        self.hooks = hooks
        self.nf = nf
        self.blur = blur
        self.last_norm = last_norm

        self.layers = self._make_layers()
        embed_dim = nf // 2
        self.last_shuf = CustomPixelShuffle_ICNR(embed_dim, embed_dim, blur=self.blur, norm_type=self.last_norm, scale=4)

        self.color_decoder = MultiScaleColorDecoder(
            in_channels=[512, 512, 256],
            num_queries=num_queries,
            num_scales=num_scales,
            dec_layers=dec_layers,
        )

    def _make_layers(self):
        decoder_layers = []
        in_c = self.hooks[-1].feature.shape[1]
        out_c = self.nf
        setup_hooks = self.hooks[-2::-1]
        for layer_index, hook in enumerate(setup_hooks):
            feature_c = hook.feature.shape[1]
            if layer_index == len(setup_hooks) - 1:
                out_c = out_c // 2
            decoder_layers.append(
                UnetBlockWide(in_c, feature_c, out_c, hook, blur=self.blur, self_attention=False, norm_type=NormType.Spectral)
            )
            in_c = out_c
        return nn.Sequential(*decoder_layers)

    def forward(self):
        encode_feat = self.hooks[-1].feature
        out0 = self.layers[0](encode_feat)
        out1 = self.layers[1](out0)
        out2 = self.layers[2](out1)
        out3 = self.last_shuf(out2)
        return self.color_decoder([out0, out1, out2], out3)


# ── Multi-Scale Color Decoder (Transformer) ──────────────────

class MultiScaleColorDecoder(nn.Module):
    def __init__(
        self,
        in_channels,
        hidden_dim=256,
        num_queries=100,
        nheads=8,
        dim_feedforward=2048,
        dec_layers=9,
        pre_norm=False,
        color_embed_dim=256,
        enforce_input_project=True,
        num_scales=3,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_queries = num_queries
        self.num_layers = dec_layers
        self.num_feature_levels = num_scales

        self.pe_layer = PositionEmbeddingSine(hidden_dim // 2, normalize=True)
        self.query_feat = nn.Embedding(num_queries, hidden_dim)
        self.query_embed = nn.Embedding(num_queries, hidden_dim)
        self.level_embed = nn.Embedding(num_scales, hidden_dim)

        self.input_proj = nn.ModuleList(
            [self._make_input_proj(in_ch, hidden_dim, enforce_input_project) for in_ch in in_channels]
        )

        self.transformer_self_attention_layers = nn.ModuleList()
        self.transformer_cross_attention_layers = nn.ModuleList()
        self.transformer_ffn_layers = nn.ModuleList()

        for _ in range(dec_layers):
            self.transformer_self_attention_layers.append(
                SelfAttentionLayer(d_model=hidden_dim, nhead=nheads, dropout=0.0, normalize_before=pre_norm)
            )
            self.transformer_cross_attention_layers.append(
                CrossAttentionLayer(d_model=hidden_dim, nhead=nheads, dropout=0.0, normalize_before=pre_norm)
            )
            self.transformer_ffn_layers.append(
                FFNLayer(d_model=hidden_dim, dim_feedforward=dim_feedforward, dropout=0.0, normalize_before=pre_norm)
            )

        self.decoder_norm = nn.LayerNorm(hidden_dim)
        self.color_embed = MLP(hidden_dim, hidden_dim, color_embed_dim, 3)

    def forward(self, x, img_features):
        src, pos = self._get_src_and_pos(x)
        bs = src[0].shape[1]
        query_embed = self.query_embed.weight.unsqueeze(1).repeat(1, bs, 1)
        output = self.query_feat.weight.unsqueeze(1).repeat(1, bs, 1)

        for i in range(self.num_layers):
            level_index = i % self.num_feature_levels
            output = self.transformer_cross_attention_layers[i](
                output, src[level_index],
                memory_mask=None, memory_key_padding_mask=None,
                pos=pos[level_index], query_pos=query_embed,
            )
            output = self.transformer_self_attention_layers[i](
                output, tgt_mask=None, tgt_key_padding_mask=None, query_pos=query_embed,
            )
            output = self.transformer_ffn_layers[i](output)

        decoder_output = self.decoder_norm(output).transpose(0, 1)
        color_embed = self.color_embed(decoder_output)
        out = torch.einsum("bqc,bchw->bqhw", color_embed, img_features)
        return out

    @staticmethod
    def _make_input_proj(in_ch, hidden_dim, enforce):
        if in_ch != hidden_dim or enforce:
            proj = nn.Conv2d(in_ch, hidden_dim, kernel_size=1)
            nn.init.kaiming_uniform_(proj.weight, a=1)
            if proj.bias is not None:
                nn.init.constant_(proj.bias, 0)
            return proj
        return nn.Sequential()

    def _get_src_and_pos(self, x):
        src, pos = [], []
        for i, feature in enumerate(x):
            pos.append(self.pe_layer(feature).flatten(2).permute(2, 0, 1))
            src.append(
                (self.input_proj[i](feature).flatten(2) + self.level_embed.weight[i][None, :, None]).permute(2, 0, 1)
            )
        return src, pos


# ── Full DDColor Model ────────────────────────────────────────

class DDColor(nn.Module):
    def __init__(
        self,
        encoder_name="convnext-l",
        num_input_channels=3,
        input_size=(256, 256),
        nf=512,
        num_output_channels=2,
        last_norm="Spectral",
        do_normalize=False,
        num_queries=256,
        num_scales=3,
        dec_layers=9,
    ):
        super().__init__()
        self.encoder = ImageEncoder(encoder_name)
        self.encoder.eval()
        test_input = torch.randn(1, num_input_channels, *input_size)
        with torch.no_grad():
            self.encoder(test_input)

        self.decoder = DuelDecoder(
            self.encoder.hooks,
            nf=nf,
            last_norm=getattr(NormType, last_norm),
            num_queries=num_queries,
            num_scales=num_scales,
            dec_layers=dec_layers,
        )

        self.refine_net = nn.Sequential(
            custom_conv_layer(num_queries + 3, num_output_channels, ks=1, use_activ=False, norm_type=NormType.Spectral)
        )

        self.do_normalize = do_normalize
        self.register_buffer("mean", torch.Tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.Tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def normalize(self, img):
        return (img - self.mean) / self.std

    def denormalize(self, img):
        return img * self.std + self.mean

    def forward(self, x):
        if x.shape[1] == 3:
            x = self.normalize(x)
        self.encoder(x)
        out_feat = self.decoder()
        coarse_input = torch.cat([out_feat, x], dim=1)
        out = self.refine_net(coarse_input)
        if self.do_normalize:
            out = self.denormalize(out)
        return out


# ── DDColor Colorizer (Colorizer ABC) ────────────────────────

MODEL_VARIANTS = {
    "modelscope": {
        "encoder_name": "convnext-l",
        "hf_repo": "piddnad/ddcolor_modelscope",
        "weight_file": "ddcolor_modelscope.pth",
        "description": "ModelScope (ConvNeXt-L, ~700 MB)",
    },
    "paper_tiny": {
        "encoder_name": "convnext-t",
        "hf_repo": "piddnad/ddcolor_paper_tiny",
        "weight_file": "ddcolor_paper_tiny.pth",
        "description": "Paper Tiny (ConvNeXt-T, ~350 MB)",
    },
}

MODEL_URLS = {
    "modelscope": "https://huggingface.co/piddnad/ddcolor_modelscope/resolve/main/pytorch_model.bin",
    "paper_tiny": "https://huggingface.co/piddnad/ddcolor_paper_tiny/resolve/main/pytorch_model.bin",
}


def load_checkpoint_state_dict(model_path):
    ckpt = torch.load(model_path, map_location="cpu")
    if isinstance(ckpt, dict) and "params" in ckpt:
        return ckpt["params"]
    return ckpt


class DDColorColorizer(Colorizer):
    def __init__(
        self,
        weight_path: str,
        device: str = "cuda:0",
        fp16: bool = False,
        input_size: int = 512,
        model_variant: str = "modelscope",
        num_queries: int = 256,
    ):
        self.weight_path = weight_path
        self.device = torch.device(device)
        self.fp16 = fp16 and device.startswith("cuda")
        self.input_size = input_size
        self.model_variant = model_variant
        self.num_queries = num_queries
        self._model = None

    def _load(self):
        if self._model is not None:
            return

        variant = MODEL_VARIANTS.get(self.model_variant, MODEL_VARIANTS["modelscope"])
        encoder_name = variant["encoder_name"]

        model = DDColor(
            encoder_name=encoder_name,
            input_size=(self.input_size, self.input_size),
            num_output_channels=2,
            last_norm="Spectral",
            do_normalize=False,
            num_queries=self.num_queries,
        )
        state_dict = load_checkpoint_state_dict(self.weight_path)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            print(f"[DDColor] Missing keys: {missing}")
        if unexpected:
            print(f"[DDColor] Unexpected keys: {unexpected}")

        model = model.to(self.device)
        model.eval()

        if self.fp16:
            model = model.half()

        self._model = model

    def colorize_frame(self, l_channel: np.ndarray) -> np.ndarray:
        self._load()
        h, w = l_channel.shape

        with torch.inference_mode():
            img_lab = np.stack([l_channel * 100.0, np.zeros_like(l_channel), np.zeros_like(l_channel)], axis=-1).astype(np.float32)
            img_gray_rgb = cv2.cvtColor(img_lab, cv2.COLOR_LAB2RGB)

            img_resized = cv2.resize(img_gray_rgb, (self.input_size, self.input_size))
            tensor = torch.from_numpy(img_resized.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)

            if self.fp16:
                tensor = tensor.half()

            output_ab = self._model(tensor).float().cpu()

            output_ab_resized = F.interpolate(output_ab, size=(h, w))[0].numpy().transpose(1, 2, 0)

        rgb = luma_to_rgb(l_channel, output_ab_resized)
        return rgb

    def colorize_batch(self, l_batch: np.ndarray) -> np.ndarray:
        self._load()
        b, h, w = l_batch.shape
        results = []

        with torch.inference_mode():
            for i in range(b):
                l_ch = l_batch[i]
                img_lab = np.stack([l_ch * 100.0, np.zeros_like(l_ch), np.zeros_like(l_ch)], axis=-1).astype(np.float32)
                img_gray_rgb = cv2.cvtColor(img_lab, cv2.COLOR_LAB2RGB)
                img_resized = cv2.resize(img_gray_rgb, (self.input_size, self.input_size))
                tensor = torch.from_numpy(img_resized.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)

                if self.fp16:
                    tensor = tensor.half()

                output_ab = self._model(tensor).float().cpu()
                output_ab_resized = F.interpolate(output_ab, size=(h, w))[0].numpy().transpose(1, 2, 0)

                rgb = luma_to_rgb(l_ch, output_ab_resized)
                results.append(rgb)

        return np.stack(results, axis=0)

    def name(self) -> str:
        return f"ddcolor_{self.model_variant}"

    def supports_batch(self) -> bool:
        return True

    def supported_filters(self) -> dict:
        return {
            "input_size": self.input_size,
            "model_variant": self.model_variant,
            "fp16": self.fp16,
        }
