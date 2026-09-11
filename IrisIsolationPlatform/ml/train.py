"""Train the production U-Net checkpoint from image/mask directory pairs."""
import argparse
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms import v2

from app.models.unet import build_unet


class IrisDataset(Dataset):
    def __init__(self, root: Path, size: int = 512) -> None:
        self.images = sorted((root / "images").glob("*"))
        self.masks = root / "masks"
        self.image_transform = v2.Compose([v2.Resize((size, size)), v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
        self.mask_transform = v2.Compose([v2.Resize((size, size)), v2.ToImage(), v2.Grayscale(), v2.ToDtype(torch.float32, scale=True)])

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, index: int):
        image_path = self.images[index]
        mask_path = self.masks / f"{image_path.stem}.png"
        return self.image_transform(Image.open(image_path).convert("RGB")), self.mask_transform(Image.open(mask_path).convert("L"))


def dice_loss(logits, targets, smooth: float = 1.0):
    probabilities = torch.sigmoid(logits)
    intersection = (probabilities * targets).sum((1, 2, 3))
    return 1 - ((2 * intersection + smooth) / (probabilities.sum((1, 2, 3)) + targets.sum((1, 2, 3)) + smooth)).mean()


def train(data: Path, output: Path, epochs: int, batch_size: int) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_unet().to(device)
    loader = DataLoader(IrisDataset(data), batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=device.type == "cuda")
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss()
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for images, masks in loader:
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = bce(logits, masks) + dice_loss(logits, masks)
            loss.backward(); optimizer.step(); total += loss.item()
        print(f"epoch={epoch + 1} loss={total / max(len(loader), 1):.4f}")
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/iris-unet.pt"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=8)
    arguments = parser.parse_args()
    train(arguments.data, arguments.output, arguments.epochs, arguments.batch_size)