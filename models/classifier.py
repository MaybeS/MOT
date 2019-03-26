from typing import Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import squeezenet1_1

from .psroi_pooling.modules.psroi_pool import PSRoIPool

from utils import image as imagelib


class Interpolate(nn.Module):
    def __init__(self, size=None, scale_factor=None, mode='nearest', align_corners=None):
        super(Interpolate, self).__init__()

        self.size = size
        self.scale_factor = scale_factor
        self.mode = mode
        self.align_corners = align_corners
        self.interpolate = F.interpolate

    def forward(self, x):
        return self.interpolate(x, size=self.size, scale_factor=self.scale_factor,
                                mode=self.mode, align_corners=self.align_corners)


class DilationLayer(nn.Module):
    def __init__(self, in_channels, out_channels,
                 kernel_size: int = 3, dilation: int = 1):
        super(DilationLayer, self).__init__()

        self.conv = nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size,
                              padding=int((kernel_size - 1) / 2 * dilation), dilation=dilation)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.relu(x)
        return x


class ConcatTable(nn.Module):
    def __init__(self, *args):
        super(ConcatTable, self).__init__()

        for i, module in enumerate(args):
            self.add_module(str(i), module)

    def __getitem__(self, idx: int):
        it = iter(self._modules.values())
        for i in range(idx):
            next(it)
        return next(it)

    def forward(self, x: torch.Tensor):
        result = None

        for module in self._modules.values():
            out = module(x)
            result = out if result is None else result + out

        return result


class Classifier(nn.Module):
    def __init__(self):
        super(Classifier, self).__init__()

        self.epoch, self.lr = 0, .01

        self.scale = 1.
        self.score = None
        self.stride = 4
        self.shape = [64, 128, 256, 512]

        # Network
        squeeze = squeezenet1_1(pretrained=True)

        self.conv1 = nn.Sequential(
            squeeze.features[0],
            squeeze.features[1],
        )
        self.conv2 = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
            squeeze.features[3],
            squeeze.features[4],
        )
        self.conv3 = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
            squeeze.features[6],
            squeeze.features[7],
        )
        self.conv4 = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
            squeeze.features[9],
            squeeze.features[10],
            squeeze.features[11],
            squeeze.features[12],
        )
        self.conv1[0].padding = (1, 1)
        self.stage_0 = nn.Sequential(
            nn.Dropout2d(inplace=True),
            nn.Conv2d(in_channels=self.shape[-1], out_channels=256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )

        feature_size = self.shape[1:]
        in_channels = 256
        out_shape = [128, 256]
        for i in range(1, len(feature_size)):
            out_channels = out_shape[-i]
            setattr(self, 'upconv_{}'.format(i),
                    nn.Sequential(
                        nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=True),
                        nn.BatchNorm2d(out_channels),
                        nn.ReLU(inplace=True),
                        Interpolate(scale_factor=2, mode='bilinear', align_corners=False),
                    ))

            feat_channels = feature_size[-1-i]
            setattr(self, 'proj_{}'.format(i), nn.Sequential(
                ConcatTable(
                    DilationLayer(feat_channels, out_channels // 2, 3, dilation=1),
                    DilationLayer(feat_channels, out_channels // 2, 5, dilation=1),
                ),
                nn.Conv2d(out_channels // 2, out_channels // 2, 1),
                nn.BatchNorm2d(out_channels // 2),
                nn.ReLU(inplace=True)
            ))
            in_channels = out_channels + out_channels // 2

        roi_size = 7
        self.cls_conv = nn.Sequential(
            nn.Conv2d(in_channels, in_channels, 3, padding=1),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),

            nn.Conv2d(in_channels, roi_size * roi_size, 1, padding=1)
        )
        self.roi_pool = PSRoIPool(roi_size, roi_size, 1. / self.stride, roi_size, 1)
        self.avg_pool = nn.AvgPool2d(roi_size, roi_size)

        # TODO: Check CUDA available
        self.cuda()
        self.eval()

    @staticmethod
    def transform(image: np.ndarray) \
            -> Tuple[np.ndarray, np.ndarray, tuple, float]:
        size = 640 if min(image.shape[0:2]) > 720 else 368

        padded, scale, shape = imagelib.factor_crop(image, size, factor=16, padding=0, based='min')

        cropped = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        cropped = cropped.astype(np.float32) / 255. - .5

        return cropped, padded, shape, scale

    def forward(self, x: torch.Tensor):
        x2 = self.conv1(x)
        x4 = self.conv2(x2)
        x8 = self.conv3(x4)
        x16 = self.conv4(x8)

        features = [x2, x4, x8, x16]
        inputs = self.stage_0(features[-1])

        for i in range(1, len(self.shape[1:])):
            depth = getattr(self, 'upconv_{}'.format(i))(inputs)
            project = getattr(self, 'proj_{}'.format(i))(features[-1-i])
            inputs = torch.cat((depth, project), 1)

        return self.cls_conv(inputs)

    def update(self, image: np.ndarray):
        cropped, padded, shape, scale = self.transform(image)

        self.scale = scale

        with torch.no_grad():
            var = torch.autograd.Variable(
                torch.from_numpy(cropped).permute(2, 0, 1).unsqueeze(0)
            ).cuda()
            self.score = self(var)

        return shape, scale

    def predict(self, rois: np.ndarray):
        rois = rois * self.scale

        size = np.size(rois, 0)
        if size <= 0:
            return np.empty([0])

        updated = torch.autograd.Variable(
            torch.from_numpy(
                np.hstack((np.zeros((np.size(rois, 0), 1), dtype=np.float32), rois))
            )
        ).cuda()

        scores = self.roi_pool(self.score, updated)
        scores = self.avg_pool(scores).view(-1)

        return torch.sigmoid(scores).data.cpu().numpy()

    def load(self, weights: str = 'data/squeezenet_small40_coco_mot16_ckpt_10.h5'):
        import h5py
        with h5py.File(weights, mode='r') as file:

            for k, v in filter(lambda kv: kv[0] in file, self.state_dict().items()):
                param = torch.from_numpy(np.asarray(file[k]))
                if v.size() == param.size():
                    v.copy_(param)

            epoch = file.attrs['epoch'] if 'epoch' in file.attrs else -1

            lr = file.attrs.get('lr', -1)
            lr = np.asarray([lr] if lr > 0 else [], dtype=np.float)

            self.epoch, self.lr = epoch, lr

            return self