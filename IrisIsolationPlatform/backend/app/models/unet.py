from pathlib import Path

import cv2
import numpy as np

from app.models.segmentation import SegmentationOutput


class UNetIrisSegmenter:
    def __init__(self, checkpoint: str, image_size: int = 512) -> None:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("Install the backend ml dependency group to use U-Net") from exc
        checkpoint_path = Path(checkpoint)
        if not checkpoint_path.is_file():
            raise RuntimeError(f"U-Net checkpoint not found: {checkpoint_path}")
        self.torch = torch
        self.image_size = image_size
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_unet().to(self.device)
        self.model.load_state_dict(torch.load(checkpoint_path, map_location=self.device, weights_only=True))
        self.model.eval()

    def segment(self, image_bytes: bytes) -> SegmentationOutput:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image could not be decoded")
        height, width = image.shape[:2]
        resized = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), (self.image_size, self.image_size))
        tensor = self.torch.from_numpy(resized).permute(2, 0, 1).float().div(255).unsqueeze(0).to(self.device)
        with self.torch.inference_mode():
            probability = self.torch.sigmoid(self.model(tensor))[0, 0].cpu().numpy()
        mask = cv2.resize(probability, (width, height), interpolation=cv2.INTER_LINEAR)
        alpha = np.uint8(np.clip(mask, 0, 1) * 255)
        output = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        output[:, :, 3] = alpha
        points = cv2.findNonZero(np.uint8(alpha > 127))
        if points is None:
            raise ValueError("U-Net did not detect an iris")
        x, y, crop_width, crop_height = cv2.boundingRect(points)
        cropped = output[y:y + crop_height, x:x + crop_width]
        ok, png = cv2.imencode(".png", cropped, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise RuntimeError("Transparent PNG encoding failed")
        foreground = mask[mask >= 0.5]
        confidence = float(foreground.mean()) if foreground.size else 0.0
        return SegmentationOutput(png.tobytes(), confidence, width, height)


def build_unet():
    import torch.nn as nn

    class DoubleConv(nn.Sequential):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__(
                nn.Conv2d(input_channels, output_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(output_channels), nn.ReLU(inplace=True),
                nn.Conv2d(output_channels, output_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(output_channels), nn.ReLU(inplace=True),
            )

    class UNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.enc1, self.enc2, self.enc3, self.enc4 = DoubleConv(3, 32), DoubleConv(32, 64), DoubleConv(64, 128), DoubleConv(128, 256)
            self.pool = nn.MaxPool2d(2)
            self.bridge = DoubleConv(256, 512)
            self.up4, self.dec4 = nn.ConvTranspose2d(512, 256, 2, 2), DoubleConv(512, 256)
            self.up3, self.dec3 = nn.ConvTranspose2d(256, 128, 2, 2), DoubleConv(256, 128)
            self.up2, self.dec2 = nn.ConvTranspose2d(128, 64, 2, 2), DoubleConv(128, 64)
            self.up1, self.dec1 = nn.ConvTranspose2d(64, 32, 2, 2), DoubleConv(64, 32)
            self.head = nn.Conv2d(32, 1, 1)

        def forward(self, value):
            e1 = self.enc1(value); e2 = self.enc2(self.pool(e1)); e3 = self.enc3(self.pool(e2)); e4 = self.enc4(self.pool(e3))
            value = self.dec4(self.torch_cat(self.up4(self.bridge(self.pool(e4))), e4))
            value = self.dec3(self.torch_cat(self.up3(value), e3))
            value = self.dec2(self.torch_cat(self.up2(value), e2))
            return self.head(self.dec1(self.torch_cat(self.up1(value), e1)))

        @staticmethod
        def torch_cat(left, right):
            import torch
            return torch.cat((left, right), dim=1)

    return UNet()