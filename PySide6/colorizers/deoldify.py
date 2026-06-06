"""DeOldify model -- pure PyTorch reimplementation matching checkpoint structure."""
from __future__ import annotations
import os, re
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np
from colorizers.base import Colorizer

MODEL_URLS = {
    "video": "https://data.deepai.org/deoldify/ColorizeVideo_gen.pth",
    "artistic": "https://data.deepai.org/deoldify/ColorizeArtistic_gen.pth",
    "stable": "https://huggingface.co/spensercai/DeOldify/resolve/main/ColorizeStable_gen.pth",
}
MODEL_FILES = {
    "video": "ColorizeVideo_gen.pth",
    "artistic": "ColorizeArtistic_gen.pth",
    "stable": "ColorizeStable_gen.pth",
}
RENDER_BASE = 16


# ---------------------------------------------------------------------------
#  Conv building blocks
# ---------------------------------------------------------------------------

def _spec_conv(ni, nf, ks=3, stride=1, padding=None, bias=True):
    if padding is None: padding = (ks - 1) // 2
    return nn.utils.spectral_norm(nn.Conv2d(ni, nf, ks, stride, padding, bias=bias))


def _wn_conv(ni, nf, ks=1):
    return nn.utils.weight_norm(nn.Conv2d(ni, nf, ks, bias=True))


def _conv_block(ni, nf, ks=3, activ=True, bn=True, sa=False):
    """SpectralNorm(conv, bias=not bn) -> [ReLU] -> [BN] -> [SelfAttention]."""
    layers = [_spec_conv(ni, nf, ks, bias=not bn)]
    if activ: layers.append(nn.ReLU(inplace=True))
    if bn:    layers.append(nn.BatchNorm2d(nf))
    if sa:    layers.append(_SelfAttention(nf))
    return nn.Sequential(*layers)


def _conv_layer(ni, nf, ks=3, activ=True, bn=True, sa=False, norm='spectral'):
    """Conv layer with optional norm type (spectral or weight)."""
    if norm == 'weight':
        conv = _wn_conv(ni, nf, ks)
    else:
        conv = _spec_conv(ni, nf, ks, bias=not bn)
    layers = [conv]
    if activ: layers.append(nn.ReLU(inplace=True))
    if bn:    layers.append(nn.BatchNorm2d(nf))
    if sa:    layers.append(_SelfAttention(nf))
    return nn.Sequential(*layers)


# ---------------------------------------------------------------------------
#  ICNR init
# ---------------------------------------------------------------------------

def _icnr(w, scale=2):
    ni, nf, h, w_ = w.shape
    ni2 = ni // (scale ** 2)
    sub = w.new_zeros(ni2, nf, h, w_)
    nn.init.kaiming_normal_(sub)
    sub = sub.transpose(0, 1).contiguous().view(nf, -1)
    sub = sub.repeat(1, scale ** 2).view(nf, ni, h, w_).transpose(0, 1)
    with torch.no_grad():
        w.copy_(sub)


# ---------------------------------------------------------------------------
#  Self-Attention
# ---------------------------------------------------------------------------

def _conv1d(ni, nf, ks=1):
    """Conv1d with spectral norm (matches fastai's conv1d)."""
    conv = nn.Conv1d(ni, nf, ks, bias=False)
    nn.init.kaiming_normal_(conv.weight)
    return nn.utils.spectral_norm(conv)


class _SelfAttention(nn.Module):
    """Self-attention layer using 1d convs (matches fastai implementation)."""
    def __init__(self, nf):
        super().__init__()
        self.query = _conv1d(nf, nf // 8)
        self.key   = _conv1d(nf, nf // 8)
        self.value = _conv1d(nf, nf)
        self.gamma = nn.Parameter(torch.tensor(0.))

    def forward(self, x):
        sz = x.shape
        x = x.view(*sz[:2], -1)
        f = self.query(x)
        g = self.key(x)
        h = self.value(x)
        beta = F.softmax(torch.bmm(f.permute(0, 2, 1).contiguous(), g), dim=1)
        o = self.gamma * torch.bmm(h, beta) + x
        return o.view(*sz).contiguous()


# ---------------------------------------------------------------------------
#  CustomPixelShuffle_ICNR  (used inside UNet blocks)
# ---------------------------------------------------------------------------

class _CustomPixelShuffleICNR(nn.Module):
    def __init__(self, ni, nf=None, scale=2, blur=True):
        super().__init__()
        nf = nf or ni
        self.conv = _conv_block(ni, nf * (scale ** 2), ks=1, activ=False, bn=True)
        _icnr(self.conv[0].weight)  # conv[0] = spectral_norm(Conv2d).weight → same object
        self.shuf = nn.PixelShuffle(scale)
        self.relu = nn.ReLU(inplace=True)
        if blur:
            self.pad  = nn.ReplicationPad2d((1, 0, 1, 0))
            self.blur = nn.AvgPool2d(2, stride=1)

    def forward(self, x):
        x = self.shuf(self.relu(self.conv(x)))
        if hasattr(self, 'blur'):
            x = self.blur(self.pad(x))
        return x


# ---------------------------------------------------------------------------
#  PixelShuffle_ICNR  (used at the end, uses weight_norm)
# ---------------------------------------------------------------------------

class _PixelShuffleICNR(nn.Module):
    def __init__(self, ni, nf=None, scale=2, blur=True):
        super().__init__()
        nf = nf or ni
        self.conv = _conv_layer(ni, nf * (scale ** 2), ks=1, activ=False, bn=False, norm='weight')
        _icnr(self.conv[0].weight)
        self.shuf = nn.PixelShuffle(scale)
        self.relu = nn.ReLU(inplace=True)
        if blur:
            self.pad  = nn.ReplicationPad2d((1, 0, 1, 0))
            self.blur = nn.AvgPool2d(2, stride=1)

    def forward(self, x):
        x = self.shuf(self.relu(self.conv(x)))
        if hasattr(self, 'blur'):
            x = self.blur(self.pad(x))
        return x


# ---------------------------------------------------------------------------
#  Hook helper
# ---------------------------------------------------------------------------

class _Hook:
    def __init__(self):
        self.stored = None
    def __call__(self, m, i, o):
        self.stored = o.detach() if o.is_meta else o


# ---------------------------------------------------------------------------
#  UnetBlockWide  (Video / Stable variant)
# ---------------------------------------------------------------------------

class _UnetBlockWide(nn.Module):
    def __init__(self, up_in_c, x_in_c, n_out, hook, blur=True, sa=False):
        super().__init__()
        self.hook = hook
        up_out = x_out = n_out // 2
        self.shuf = _CustomPixelShuffleICNR(up_in_c, up_out, blur=blur)
        self.bn   = nn.BatchNorm2d(x_in_c)
        ni = up_out + x_in_c
        self.conv = _conv_block(ni, x_out, sa=sa)

    def forward(self, up_in):
        s = self.hook.stored
        up_out = self.shuf(up_in)
        if s.shape[-2:] != up_out.shape[-2:]:
            up_out = F.interpolate(up_out, s.shape[-2:], mode='nearest')
        return self.conv(torch.cat([up_out, self.bn(s)], dim=1))


# ---------------------------------------------------------------------------
#  UnetBlockDeep  (Artistic variant)
# ---------------------------------------------------------------------------

class _UnetBlockDeep(nn.Module):
    def __init__(self, up_in_c, x_in_c, hook, final_div=True, blur=True, nf_factor=1.5, sa=False):
        super().__init__()
        self.hook = hook
        self.shuf = _CustomPixelShuffleICNR(up_in_c, up_in_c // 2, blur=blur)
        self.bn   = nn.BatchNorm2d(x_in_c)
        ni = up_in_c // 2 + x_in_c
        nf = int((ni if final_div else ni // 2) * nf_factor)
        self.conv1 = _conv_block(ni, nf, sa=False)
        self.conv2 = _conv_block(nf, nf, sa=sa)

    def forward(self, up_in):
        s = self.hook.stored
        up_out = self.shuf(up_in)
        if s.shape[-2:] != up_out.shape[-2:]:
            up_out = F.interpolate(up_out, s.shape[-2:], mode='nearest')
        return self.conv2(self.conv1(torch.cat([up_out, self.bn(s)], dim=1)))


# ---------------------------------------------------------------------------
#  Generator  --  uses layers named l0, l1, ... to match checkpoint keys
# ---------------------------------------------------------------------------

class DeOldifyGenerator(nn.Module):
    """Mirrors DynamicUnetWide/DynamicUnetDeep structure.
    Submodules are named l0, l1, ... so that state_dict keys align with
    checkpoints stored as SequentialEx (keys like 'layers.0.encoder...')."""

    def __init__(self, variant='video'):
        super().__init__()
        self.variant = variant
        self.nf_factor = 2.0 if variant != 'artistic' else 1.5
        self.nf = int(512 * self.nf_factor)
        self.arch_name = 'resnet101' if variant != 'artistic' else 'resnet34'
        self.blur = True
        self.self_attention = True
        self.last_cross = True

        # --- build encoder ---
        enc = self._build_encoder()
        self.l0 = enc  # layers.0

        # --- determine skip indices by running the encoder ---
        sfs_szs, sfs_idxs = self._compute_sfs(enc)

        # --- initial layers ---
        ni = sfs_szs[-1][1]
        self.l1 = nn.BatchNorm2d(ni)  # layers.1
        self.l2 = nn.ReLU(inplace=True)  # layers.2

        # middle_conv
        mid0 = _conv_block(ni, ni * 2)
        mid1 = _conv_block(ni * 2, ni)
        self.l3 = nn.Sequential(mid0, mid1)  # layers.3

        # run middle_conv to get shape for unet blocks
        with torch.no_grad():
            dummy = torch.zeros(1, ni, sfs_szs[-1][2], sfs_szs[-1][3])
            x = self.l3(dummy)

        # --- hooks for skip connections ---
        self._sfs_hooks = []
        for i, idx in enumerate(sfs_idxs):
            h = _Hook()
            enc[idx].register_forward_hook(h)
            self._sfs_hooks.append(h)

        # --- unet blocks (layers 4..7) ---
        n_blocks = len(sfs_idxs)
        with torch.no_grad():
            _ = enc(torch.zeros(1, 3, 256, 256))

        for i, idx in enumerate(sfs_idxs):
            not_final = i != n_blocks - 1
            up_in_c = int(x.shape[1])
            x_in_c  = int(sfs_szs[idx][1])
            sa = self.self_attention and (i == n_blocks - 3)

            if variant == 'artistic':
                blk = _UnetBlockDeep(up_in_c, x_in_c, self._sfs_hooks[i],
                                     final_div=not_final,
                                     nf_factor=self.nf_factor, sa=sa)
            else:
                n_out = self.nf if not_final else self.nf // 2
                blk = _UnetBlockWide(up_in_c, x_in_c, n_out, self._sfs_hooks[i], sa=sa)

            setattr(self, f'l{4 + i}', blk)

            with torch.no_grad():
                blk.eval()
                x = blk(x)

        ni_out = int(x.shape[1])

        # --- PixelShuffle_ICNR (layer 8) ---
        self.l8 = _PixelShuffleICNR(ni_out, blur=True)
        with torch.no_grad():
            x = self.l8(x)
        ni_ps = int(x.shape[1])

        # --- MergeLayer (layer 9, no params) + res_block (layer 10) ---
        self.merge_cat_size = ni_ps + 3  # in_channels(encoder) = 3

        # res_block: fastai's res_block(259, bottle=False, norm_type=Spectral) is:
        # SequentialEx(conv_layer=Sequential[spec_conv, ReLU],
        #              conv_layer=Sequential[spec_conv, ReLU],
        #              MergeLayer(False))
        self.l10 = nn.ModuleList([
            nn.Sequential(_spec_conv(self.merge_cat_size, self.merge_cat_size, ks=3, bias=True),
                          nn.ReLU(inplace=True)),
            nn.Sequential(_spec_conv(self.merge_cat_size, self.merge_cat_size, ks=3, bias=True),
                          nn.ReLU(inplace=True)),
        ])

        # --- final conv (layer 11) ---
        self.l11 = nn.Sequential(
            _spec_conv(self.merge_cat_size, 3, ks=1),
        )

        # register hook on encoder input for merge
        self.enc_in = None
        self.enc_hook_handle = None

        # store sfs_idxs for forward pass
        self.sfs_idxs = sfs_idxs

    def _build_encoder(self):
        import torchvision.models as M
        if self.arch_name == 'resnet101':
            m = M.resnet101(weights='IMAGENET1K_V1')
        else:
            m = M.resnet34(weights='IMAGENET1K_V1')
        return nn.Sequential(*list(m.children())[:8])

    def _compute_sfs(self, enc):
        """Compute model sizes and skip indices, mirroring fastai's logic."""
        sizes = []
        hooks = []
        for child in enc.children():
            h = _Hook()
            child.register_forward_hook(h)
            hooks.append(h)
        with torch.no_grad():
            enc(torch.zeros(1, 3, 256, 256))
        sizes = [h.stored.shape for h in hooks]

        feature_szs = [s[-1] for s in sizes]
        sfs_idxs = list(np.where(np.array(feature_szs[:-1]) != np.array(feature_szs[1:]))[0])
        if feature_szs[0] != feature_szs[1]:
            sfs_idxs = [0] + sfs_idxs
        sfs_idxs = list(reversed(sfs_idxs))
        return sizes, sfs_idxs

    def forward(self, x):
        self.enc_in = x
        x = self.l0(x)
        x = self.l1(x)
        x = self.l2(x)
        x = self.l3(x)
        x = self.l4(x)
        if hasattr(self, 'l5'): x = self.l5(x)
        if hasattr(self, 'l6'): x = self.l6(x)
        if hasattr(self, 'l7'): x = self.l7(x)
        x = self.l8(x)
        # MergeLayer(dense=True): cat with encoder input
        orig = self.enc_in
        if orig.shape[-2:] != x.shape[-2:]:
            orig = F.interpolate(orig, x.shape[-2:], mode='nearest')
        x = torch.cat([x, orig], dim=1)

        # res_block (layer 10): x_in -> conv1 -> conv2 -> + x_in (residual)
        res_in = x
        for l in self.l10:
            res_in = l(res_in)
        x = x + res_in  # MergeLayer(dense=False): x + x.orig

        x = self.l11(x)
        return torch.sigmoid(x) * 6 - 3  # y_range = (-3, 3)

    def load_deoldify_weights(self, path, strict=True):
        raw = torch.load(path, map_location='cpu', weights_only=False)
        sd = raw.get('model', raw)
        if any(k.startswith('model.') for k in sd):
            sd = {k[6:]: v for k, v in sd.items()}

        self._valid_names = self._build_name_set(self)
        key_map = {}
        for ckpt_key, wt in sd.items():
            mapped = self._map_key(ckpt_key)
            if mapped is not None:
                key_map[mapped] = wt

        errs = self.load_state_dict(key_map, strict=False)
        ckpt_names = set(sd.keys())
        unmatched_ckpt = [k for k in sd if self._map_key(k) is None]
        if strict:
            if errs[0]:
                print(f'Missing keys ({len(errs[0])}):', list(errs[0])[:5])
            if errs[1]:
                print(f'Unexpected keys ({len(errs[1])}):', list(errs[1])[:5])
            if unmatched_ckpt:
                print(f'Unmapped checkpoint keys ({len(unmatched_ckpt)}):', unmatched_ckpt[:5])
        return errs

    @staticmethod
    def _build_name_set(module):
        """Build set of valid param/buffer names for fast lookup."""
        names = set()
        for k, _ in module.named_parameters():
            names.add(k)
        for k, _ in module.named_buffers():
            names.add(k)
        return names

    def _map_key(self, key):
        """Map sequential-ex checkpoint key to our named-module key."""
        m = re.match(r'^layers\.(\d+)(.*)$', key)
        if not m:
            return None
        layer_num = int(m.group(1))
        rest = m.group(2)
        valid = self._valid_names

        # try direct: lN.{rest}
        mapped = f'l{layer_num}{rest}'
        if mapped in valid:
            return mapped

        # try stripping .layers. (for res_block inside SequentialEx)
        stripped = rest.replace('.layers.', '.')
        mapped = f'l{layer_num}{stripped}'
        if mapped in valid:
            return mapped

        # try removing an extra '.0' layer that SequentialEx may add
        if rest.startswith('.layers.'):
            stripped2 = '.' + rest[len('.layers.'):]
            mapped = f'l{layer_num}{stripped2}'
            if mapped in valid:
                return mapped

        return None


# ---------------------------------------------------------------------------
#  Colorizer wrapper
# ---------------------------------------------------------------------------

class DeOldifyColorizer(Colorizer):
    def __init__(self, weight_path, device='cuda:0', fp16=True,
                 render_factor=21, model_variant='video'):
        self.weight_path = weight_path
        self.device_str = device
        self.fp16 = fp16
        self._rf = render_factor
        self.variant = model_variant
        self._model = None
        self._dev = None

    @property
    def render_factor(self): return self._rf

    def set_render_factor(self, v):
        self._rf = max(10, min(45, v))

    def _lazy(self):
        if self._model is not None:
            return
        self._dev = torch.device(self.device_str if torch.cuda.is_available() else 'cpu')
        if not os.path.exists(self.weight_path):
            raise FileNotFoundError(
                f'Weights not found: {self.weight_path}\n'
                f'Download: {MODEL_URLS.get(self.variant, "")}'
            )
        self._model = DeOldifyGenerator(self.variant)
        self._model.load_deoldify_weights(self.weight_path, strict=False)
        self._model = self._model.to(self._dev).eval()
        if self.fp16 and 'cuda' in str(self._dev):
            self._model = self._model.half()

    def name(self): return f'deoldify_{self.variant}'
    def supports_batch(self): return False
    def supported_filters(self): return {'render_factor': True, 'model_variant': True}

    def _pre(self, l_ch):
        import cv2
        h, w = l_ch.shape[:2]
        sz = self._rf * RENDER_BASE
        rgb = np.stack([l_ch] * 3, axis=-1).astype(np.float32)
        sq = cv2.resize(rgb, (sz, sz), interpolation=cv2.INTER_LINEAR)
        t = torch.from_numpy(sq.transpose(2, 0, 1)).unsqueeze(0)
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        return (t - mean) / std, h, w

    def _post(self, ot, oh, ow, ol):
        import cv2
        out = ot.squeeze(0).cpu().numpy().transpose(1, 2, 0)
        out = cv2.resize(out, (ow, oh), interpolation=cv2.INTER_LINEAR)
        out_u8 = (out * 255).astype(np.uint8)
        cyuv = cv2.cvtColor(out_u8, cv2.COLOR_RGB2YUV)
        oyuv = cv2.cvtColor((np.stack([ol] * 3, -1) * 255).astype(np.uint8), cv2.COLOR_RGB2YUV)
        r = oyuv.copy()
        r[:, :, 1:] = cyuv[:, :, 1:]
        return cv2.cvtColor(r, cv2.COLOR_YUV2RGB)

    def colorize_frame(self, l):
        self._lazy()
        t, h, w = self._pre(l)
        t = t.to(self._dev)
        if self.fp16 and 'cuda' in str(self._dev):
            t = t.half()
        with torch.no_grad():
            o = self._model(t)
            mean = torch.tensor([0.485, 0.456, 0.406], device=o.device, dtype=o.dtype).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225], device=o.device, dtype=o.dtype).view(1, 3, 1, 1)
            o = (o * std + mean).clamp(0, 1)
        return self._post(o, h, w, l)

    def colorize_batch(self, b):
        return np.stack([self.colorize_frame(b[i]) for i in range(b.shape[0])])

    def reset_temporal_state(self): pass

    def to(self, d):
        if self._model is not None:
            self._model = self._model.to(d)
        self.device_str = str(d)
        return self
