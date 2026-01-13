"""
ML Genre Classifier - GTZAN-trained model for real-time genre detection
Trained on 1000 tracks (100 per genre × 10 genres) with 58 audio features
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
import warnings
warnings.filterwarnings('ignore')

# Paths
DATASET_PATH = Path(__file__).parent.parent / "music_dataset" / "Data"
FEATURES_FILE = DATASET_PATH / "features_30_sec.csv"
FEATURES_3SEC_FILE = DATASET_PATH / "features_3_sec.csv"
MODEL_PATH = Path(__file__).parent.parent / "models"

# GTZAN genre labels (10 genres)
GTZAN_GENRES = ['blues', 'classical', 'country', 'disco', 'hiphop', 
                'jazz', 'metal', 'pop', 'reggae', 'rock']

# Feature columns used for classification (exclude filename, length, label)
FEATURE_COLUMNS = [
    'chroma_stft_mean', 'chroma_stft_var',
    'rms_mean', 'rms_var',
    'spectral_centroid_mean', 'spectral_centroid_var',
    'spectral_bandwidth_mean', 'spectral_bandwidth_var',
    'rolloff_mean', 'rolloff_var',
    'zero_crossing_rate_mean', 'zero_crossing_rate_var',
    'harmony_mean', 'harmony_var',
    'perceptr_mean', 'perceptr_var',
    'tempo',
    'mfcc1_mean', 'mfcc1_var', 'mfcc2_mean', 'mfcc2_var',
    'mfcc3_mean', 'mfcc3_var', 'mfcc4_mean', 'mfcc4_var',
    'mfcc5_mean', 'mfcc5_var', 'mfcc6_mean', 'mfcc6_var',
    'mfcc7_mean', 'mfcc7_var', 'mfcc8_mean', 'mfcc8_var',
    'mfcc9_mean', 'mfcc9_var', 'mfcc10_mean', 'mfcc10_var',
    'mfcc11_mean', 'mfcc11_var', 'mfcc12_mean', 'mfcc12_var',
    'mfcc13_mean', 'mfcc13_var', 'mfcc14_mean', 'mfcc14_var',
    'mfcc15_mean', 'mfcc15_var', 'mfcc16_mean', 'mfcc16_var',
    'mfcc17_mean', 'mfcc17_var', 'mfcc18_mean', 'mfcc18_var',
    'mfcc19_mean', 'mfcc19_var', 'mfcc20_mean', 'mfcc20_var'
]


class GenreClassifier:
    """
    ML-based genre classifier trained on GTZAN dataset.
    Uses Random Forest for robust multi-class classification.
    """
    
    def __init__(self, model_name="genre_classifier_rf"):
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.model_name = model_name
        self.model_file = MODEL_PATH / f"{model_name}.pkl"
        self.is_trained = False
        self.accuracy = 0.0
        
        # Try to load pre-trained model
        if self.model_file.exists():
            self._load_model()
    
    def _load_model(self):
        """Load pre-trained model from disk."""
        try:
            with open(self.model_file, 'rb') as f:
                data = pickle.load(f)
            
            self.model = data['model']
            self.scaler = data['scaler']
            self.label_encoder = data['label_encoder']
            self.accuracy = data.get('accuracy', 0.0)
            self.is_trained = True
            print(f"✅ Loaded genre classifier: {self.model_file.name} (accuracy: {self.accuracy:.1%})")
            return True
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            return False
    
    def _save_model(self):
        """Save trained model to disk."""
        MODEL_PATH.mkdir(parents=True, exist_ok=True)
        
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'label_encoder': self.label_encoder,
            'accuracy': self.accuracy,
            'feature_columns': FEATURE_COLUMNS,
            'genres': GTZAN_GENRES
        }
        
        with open(self.model_file, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"💾 Model saved: {self.model_file}")
    
    def train(self, use_3sec_segments=True, test_size=0.2):
        """
        Train the genre classifier on GTZAN dataset.
        
        Args:
            use_3sec_segments: Use 3-second segments (more data) vs 30-second (less data)
            test_size: Fraction of data for testing
        
        Returns:
            Accuracy score on test set
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler, LabelEncoder
        from sklearn.metrics import classification_report, confusion_matrix
        
        # Load features
        features_file = FEATURES_3SEC_FILE if use_3sec_segments else FEATURES_FILE
        
        if not features_file.exists():
            print(f"❌ Features file not found: {features_file}")
            return 0.0
        
        print(f"📂 Loading features from: {features_file.name}")
        df = pd.read_csv(features_file)
        print(f"   Loaded {len(df)} samples")
        
        # Prepare features and labels
        X = df[FEATURE_COLUMNS].values
        y = df['label'].values
        
        # Handle any NaN values
        X = np.nan_to_num(X, nan=0.0)
        
        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(np.asarray(y))
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=test_size, random_state=42, stratify=y_encoded
        )
        
        print(f"   Training: {len(X_train)} samples | Testing: {len(X_test)} samples")
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train Random Forest
        print("🌲 Training Random Forest classifier...")
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            n_jobs=-1,
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        self.accuracy = (y_pred == y_test).mean()
        
        print(f"\n📊 Test Accuracy: {self.accuracy:.1%}")
        print("\n" + "=" * 50)
        print("Classification Report:")
        print("=" * 50)
        print(classification_report(
            y_test, y_pred, 
            target_names=self.label_encoder.classes_
        ))
        
        # Feature importance
        importances = self.model.feature_importances_
        top_features = sorted(
            zip(FEATURE_COLUMNS, importances), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        print("\n🔑 Top 10 Most Important Features:")
        for feat, imp in top_features:
            print(f"   {feat}: {imp:.4f}")
        
        self.is_trained = True
        
        # Save the model
        self._save_model()
        
        return self.accuracy
    
    def predict(self, features, return_probabilities=False):
        """
        Predict genre from audio features.
        
        Args:
            features: numpy array of shape (n_features,) or (n_samples, n_features)
            return_probabilities: Return probability distribution over genres
        
        Returns:
            Predicted genre(s) and optionally probabilities
        """
        if not self.is_trained or self.scaler is None or self.model is None or self.label_encoder is None:
            print("❌ Model not trained! Call train() first or load a pre-trained model.")
            return None
        
        # Ensure 2D array
        features = np.array(features)
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        # Handle NaN
        features = np.nan_to_num(features, nan=0.0)
        
        # Scale
        features_scaled = self.scaler.transform(features)
        
        # Predict
        predictions = self.model.predict(features_scaled)
        genres = self.label_encoder.inverse_transform(predictions)
        
        if return_probabilities:
            probabilities = self.model.predict_proba(features_scaled)
            return genres, probabilities
        
        return genres
    
    def predict_with_confidence(self, features):
        """
        Predict genre with confidence score.
        
        Returns:
            Dict with 'genre', 'confidence', and 'all_probabilities'
        """
        if not self.is_trained or self.label_encoder is None:
            return {'genre': 'unknown', 'confidence': 0.0, 'all_probabilities': {}}
        
        prediction_result = self.predict(features, return_probabilities=True)
        if prediction_result is None:
            return {'genre': 'unknown', 'confidence': 0.0, 'all_probabilities': {}}
        
        genres, probs = prediction_result
        
        # Get top prediction
        top_genre = genres[0]
        top_prob = probs[0].max()
        
        # All probabilities
        all_probs = dict(zip(self.label_encoder.classes_, probs[0]))
        
        # Top 3 predictions
        sorted_probs = sorted(all_probs.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'genre': top_genre,
            'confidence': float(top_prob),
            'top_3': sorted_probs,
            'all_probabilities': all_probs
        }


class LiveAudioAnalyzer:
    """
    Real-time audio feature extraction for live genre classification.
    Uses librosa for feature extraction (same as GTZAN dataset).
    """
    
    def __init__(self, classifier=None):
        self.classifier = classifier or GenreClassifier()
        self._librosa_available = False
        self._check_librosa()
    
    def _check_librosa(self):
        """Check if librosa is available for feature extraction."""
        try:
            import librosa
            self._librosa_available = True
            print("✅ Librosa available for live audio analysis")
        except ImportError:
            print("⚠️ Librosa not installed. Install with: pip install librosa")
            self._librosa_available = False
    
    def extract_features_from_audio(self, audio_data, sr=22050):
        """
        Extract GTZAN-compatible features from audio data.
        
        Args:
            audio_data: numpy array of audio samples
            sr: sample rate (default 22050 Hz, GTZAN standard)
        
        Returns:
            numpy array of features matching FEATURE_COLUMNS order
        """
        if not self._librosa_available:
            print("❌ Librosa required for feature extraction")
            return None
        
        import librosa
        
        # Ensure float32
        y = audio_data.astype(np.float32)
        
        features = []
        
        # Chroma STFT
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        features.extend([chroma.mean(), chroma.var()])
        
        # RMS Energy
        rms = librosa.feature.rms(y=y)
        features.extend([rms.mean(), rms.var()])
        
        # Spectral Centroid
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        features.extend([cent.mean(), cent.var()])
        
        # Spectral Bandwidth
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        features.extend([bandwidth.mean(), bandwidth.var()])
        
        # Spectral Rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        features.extend([rolloff.mean(), rolloff.var()])
        
        # Zero Crossing Rate
        zcr = librosa.feature.zero_crossing_rate(y)
        features.extend([zcr.mean(), zcr.var()])
        
        # Harmony and Perceptr (using harmonic/percussive separation)
        y_harm, y_perc = librosa.effects.hpss(y)
        features.extend([y_harm.mean(), y_harm.var()])
        features.extend([y_perc.mean(), y_perc.var()])
        
        # Tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        features.append(float(tempo))
        
        # MFCCs (20 coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        for i in range(20):
            features.extend([mfccs[i].mean(), mfccs[i].var()])
        
        return np.array(features)
    
    def extract_features_from_file(self, filepath, duration=30):
        """
        Extract features from an audio file.
        
        Args:
            filepath: Path to audio file
            duration: Duration to analyze (seconds)
        
        Returns:
            numpy array of features
        """
        if not self._librosa_available:
            return None
        
        import librosa
        
        try:
            y, sr = librosa.load(filepath, duration=duration, sr=22050)
            return self.extract_features_from_audio(y, int(sr))
        except Exception as e:
            print(f"❌ Error loading audio file: {e}")
            return None
    
    def classify_audio(self, audio_data=None, filepath=None, sr=22050):
        """
        Classify audio genre from data or file.
        
        Returns:
            Dict with genre, confidence, and top predictions
        """
        if filepath:
            features = self.extract_features_from_file(filepath)
        elif audio_data is not None:
            features = self.extract_features_from_audio(audio_data, sr)
        else:
            print("❌ Provide audio_data or filepath")
            return None
        
        if features is None:
            return None
        
        return self.classifier.predict_with_confidence(features)


# ========== CLI ==========

if __name__ == "__main__":
    print("=" * 60)
    print("  GTZAN Genre Classifier - ML Training & Testing")
    print("=" * 60)
    
    classifier = GenreClassifier()
    
    # Train if not already trained
    if not classifier.is_trained:
        print("\n🎓 Training new model on GTZAN dataset...")
        accuracy = classifier.train(use_3sec_segments=True)
    else:
        print(f"\n✅ Using pre-trained model (accuracy: {classifier.accuracy:.1%})")
    
    # Test predictions
    if classifier.is_trained:
        print("\n" + "-" * 60)
        print("Testing predictions on sample data...")
        print("-" * 60)
        
        # Load a few test samples
        if FEATURES_FILE.exists():
            df = pd.read_csv(FEATURES_FILE)
            
            # Test on random samples from each genre
            for genre in GTZAN_GENRES[:5]:  # Test 5 genres
                sample = df[df['label'] == genre].iloc[0]
                features = sample[FEATURE_COLUMNS].values
                
                result = classifier.predict_with_confidence(features)
                
                correct = "✅" if result['genre'] == genre else "❌"
                print(f"{correct} Actual: {genre:10} | Predicted: {result['genre']:10} ({result['confidence']:.1%})")
    
    print("\n" + "=" * 60)
    print("Model ready for integration with audio_intelligence.py")
    print("=" * 60)
