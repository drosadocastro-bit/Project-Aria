"""Analyze the genre classifier model"""
import joblib
import warnings
warnings.filterwarnings('ignore')

model_path = "models/genre_classifier_model.pkl"

print(f"=== Analyzing: {model_path} ===\n")

# Check file size
import os
size_mb = os.path.getsize(model_path) / (1024 * 1024)
print(f"File size: {size_mb:.2f} MB\n")

# Load with joblib
model = joblib.load(model_path)

print(f"Type: {type(model).__name__}")

# Pipeline steps
if hasattr(model, 'steps'):
    print(f"\n📊 Pipeline Steps:")
    for name, step in model.steps:
        print(f"  {name}: {type(step).__name__}")
        
        # Vectorizer details
        if hasattr(step, 'vocabulary_'):
            print(f"    └─ Vocabulary size: {len(step.vocabulary_)}")
            sample = list(step.vocabulary_.keys())[:5]
            print(f"    └─ Sample features: {sample}")
        
        # Classifier details
        if hasattr(step, 'classes_'):
            classes = list(step.classes_)
            print(f"    └─ Classes ({len(classes)}): {classes[:10]}...")
            print(f"    └─ Full class list: {classes}")

# Check if we can predict
print("\n🔮 Model Capabilities:")
print(f"  Can predict: {hasattr(model, 'predict')}")
print(f"  Can predict_proba: {hasattr(model, 'predict_proba')}")

# Test prediction
print("\n🧪 Test Prediction:")
test_texts = [
    "heavy metal guitar solo drums",
    "hip hop beats rap flow",
    "electronic synth dance edm",
    "country guitar acoustic folk",
    "jazz piano saxophone blues"
]
for text in test_texts:
    try:
        pred = model.predict([text])[0]
        proba = model.predict_proba([text]).max()
        print(f"  '{text[:30]}...' → {pred} ({proba:.1%})")
    except Exception as e:
        print(f"  Error: {e}")

