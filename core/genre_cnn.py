"""
PyTorch CNN Genre Classifier
Trains on GTZAN spectrogram images (music_dataset/Data/images_original)
Provides lightweight audio prediction using mel-spectrograms.
"""

import argparse
import json
from pathlib import Path
import os
from typing import Optional, cast

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms

from core.listener_profile import ListenerProfile


DATASET_IMAGES = Path(__file__).parent.parent / "music_dataset" / "Data" / "images_original"
MODELS_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODELS_DIR / "genre_cnn.pt"
LABELS_PATH = MODELS_DIR / "genre_cnn_labels.json"


class SmallCNN(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 28 * 28, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x


def build_mobilenet_v2(num_classes: int):
    from torchvision import models
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    return model


def build_class_weights(labels):
    """Build class weights from listener profile affinities and skip rates."""
    profile = ListenerProfile()
    weights = []
    for label in labels:
        affinity = profile.get_genre_affinity(label)
        skip_rate = profile.get_skip_rate_for_genre(label)
        # Base weight around 1.0, boost favorites, dampen high-skip genres
        weight = 1.0 + (affinity - 0.5) * 0.6
        if skip_rate > 0.5:
            weight -= 0.2
        weight = max(0.5, min(1.5, weight))
        weights.append(weight)
    return torch.tensor(weights, dtype=torch.float32)


class CNNGenreClassifier:
    def __init__(self, model_path: Path = MODEL_PATH, labels_path: Path = LABELS_PATH, device: Optional[str] = None, backbone: str = "small"):
        self.model_path = Path(model_path)
        self.labels_path = Path(labels_path)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.labels = None
        self.is_trained = False
        self.backbone = backbone

        if self.model_path.exists() and self.labels_path.exists():
            self._load()

    def _load(self):
        with open(self.labels_path, "r", encoding="utf-8") as f:
            self.labels = json.load(f)
        if self.backbone == "mobilenet_v2":
            self.model = build_mobilenet_v2(num_classes=len(self.labels))
        else:
            self.model = SmallCNN(num_classes=len(self.labels))
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
        self.is_trained = True

    def _transform(self):
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def predict_image(self, image_path: Path):
        if not self.is_trained:
            return None
        assert self.model is not None
        assert self.labels is not None
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        tensor = cast(torch.Tensor, self._transform()(img))
        tensor = tensor.unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        return self._format_prediction(probs)

    def predict_audio(self, audio_path: Path, target_sr: int = 22050):
        if not self.is_trained:
            return None
        assert self.model is not None
        assert self.labels is not None

        try:
            import importlib
            torchaudio = importlib.import_module("torchaudio")
            transforms_mod = importlib.import_module("torchaudio.transforms")
            MelSpectrogram = getattr(transforms_mod, "MelSpectrogram")
            AmplitudeToDB = getattr(transforms_mod, "AmplitudeToDB")
        except Exception:
            return None

        waveform, sr = torchaudio.load(audio_path)
        if sr != target_sr:
            waveform = torchaudio.functional.resample(waveform, sr, target_sr)

        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        mel = MelSpectrogram(sample_rate=target_sr, n_mels=128, n_fft=2048, hop_length=512)(waveform)
        mel_db = AmplitudeToDB()(mel).squeeze(0)
        mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)

        # Convert to 3-channel image tensor
        mel_img = mel_db.unsqueeze(0).repeat(3, 1, 1)
        mel_img = torch.nn.functional.interpolate(mel_img.unsqueeze(0), size=(224, 224), mode="bilinear", align_corners=False)
        mel_img = mel_img.to(self.device)

        with torch.no_grad():
            logits = self.model(mel_img)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        return self._format_prediction(probs)

    def _format_prediction(self, probs):
        if not self.labels:
            return None
        idx = int(probs.argmax())
        confidence = float(probs[idx])
        top_3_idx = probs.argsort()[-3:][::-1]
        top_3 = [(self.labels[i], float(probs[i])) for i in top_3_idx]
        return {
            "genre": self.labels[idx],
            "confidence": confidence,
            "top_3": top_3,
            "all_probabilities": {self.labels[i]: float(probs[i]) for i in range(len(self.labels))}
        }


def train(epochs=8, batch_size=32, lr=1e-3, train_split=0.8, augment=False, backbone="small", profile_bias=False):
    if not DATASET_IMAGES.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_IMAGES}")

    if augment:
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(8),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    dataset = datasets.ImageFolder(DATASET_IMAGES, transform=transform)
    labels = dataset.classes

    train_size = int(len(dataset) * train_split)
    val_size = len(dataset) - train_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=2)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if backbone == "mobilenet_v2":
        model = build_mobilenet_v2(num_classes=len(labels)).to(device)
    else:
        model = SmallCNN(num_classes=len(labels)).to(device)

    if profile_bias:
        class_weights = build_class_weights(labels).to(device)
        print("[INFO] Using listener profile class weights for biasing")
        criterion = nn.CrossEntropyLoss(weight=class_weights)
    else:
        criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

        train_acc = correct / max(1, total)
        print(f"Epoch {epoch+1}/{epochs} | Loss: {running_loss:.3f} | Train Acc: {train_acc:.1%}")

    # Validation
    model.eval()
    val_correct = 0
    val_total = 0
    with torch.no_grad():
        for images, targets in val_loader:
            images, targets = images.to(device), targets.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)
            val_total += targets.size(0)
            val_correct += predicted.eq(targets).sum().item()

    val_acc = val_correct / max(1, val_total)
    print(f"Validation Accuracy: {val_acc:.1%}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2)

    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved labels: {LABELS_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Train/evaluate CNN genre classifier (PyTorch)")
    parser.add_argument("--train", action="store_true", help="Train CNN on spectrogram images")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--backbone", type=str, default="small", choices=["small", "mobilenet_v2"], help="Model backbone")
    parser.add_argument("--augment", action="store_true", help="Use data augmentation")
    parser.add_argument("--profile-bias", action="store_true", help="Bias training toward listener profile preferences")
    parser.add_argument("--predict-audio", type=str, help="Predict from an audio file")
    parser.add_argument("--predict-image", type=str, help="Predict from an image file")

    args = parser.parse_args()

    if args.train:
        train(
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            augment=args.augment,
            backbone=args.backbone,
            profile_bias=args.profile_bias,
        )
        return

    clf = CNNGenreClassifier(backbone=args.backbone)
    if not clf.is_trained:
        print("Model not trained. Run: python -m core.genre_cnn --train")
        return

    if args.predict_image:
        result = clf.predict_image(Path(args.predict_image))
        print(result)
    elif args.predict_audio:
        result = clf.predict_audio(Path(args.predict_audio))
        print(result)
    else:
        print("No action specified. Use --train or --predict-*.")


if __name__ == "__main__":
    main()
