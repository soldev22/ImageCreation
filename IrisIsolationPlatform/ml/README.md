# U-Net Training

Place matching source images and binary PNG masks under `dataset/images` and `dataset/masks`. Mask filenames must match image stems. From the backend virtual environment with the `ml` extras installed:

```powershell
$env:PYTHONPATH = "..\backend"
python train.py --data dataset --output models/iris-unet.pt --epochs 40
```

Use subject-disjoint train/validation/test splits to avoid identity leakage. Track Dice score, intersection-over-union, boundary F1, false acceptance, and performance across eye color, skin tone, illumination, eyewear, and capture devices. Do not deploy a checkpoint until the model card records dataset consent, limitations, and subgroup evaluation.
