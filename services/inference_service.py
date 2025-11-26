# services/inference_service.py
"""
AI Inference service using ONNX models.
Models are trained separately and converted to ONNX format (~5-10MB each).
"""

import onnxruntime as ort
import numpy as np
import os
from pathlib import Path
from typing import List, Dict
import json

# Path to ONNX models
MODEL_DIR = Path(__file__).parent.parent / "ml_models"


class AIInferenceEngine:
    """
    ONNX runtime inference engine for student performance prediction.
    Lightweight and fast - perfect for Vercel deployment.
    """
    
    def __init__(self, model_name: str):
        """
        Initialize ONNX runtime session.
        
        Args:
            model_name: Name of ONNX model file (e.g., 'passing_predictor.onnx')
        """
        self.model_path = MODEL_DIR / model_name
        self.session = None
        self.input_name = None
        self.output_names = None
        
        # Load model info if available
        self.model_info = self._load_model_info()
        
        # Lazy loading: Only load when first prediction is made
        if self.model_path.exists():
            self._initialize_session()
        else:
            print(f"⚠️  Warning: Model {model_name} not found at {self.model_path}")
            print(f"💡 Train models using cognify_ml_training pipeline")
    
    def _initialize_session(self):
        """Initialize ONNX runtime session."""
        try:
            # Create session with optimizations
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options
            )
            
            # Get input/output names
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [output.name for output in self.session.get_outputs()]
            
            print(f"✅ Loaded ONNX model: {self.model_path.name}")
            
        except Exception as e:
            print(f"❌ Failed to load ONNX model {self.model_path.name}: {str(e)}")
            self.session = None
    
    def _load_model_info(self) -> Dict:
        """Load model metadata."""
        info_path = MODEL_DIR / "model_info.json"
        if info_path.exists():
            with open(info_path, 'r') as f:
                return json.load(f)
        return {}
    
    def predict(self, input_features: List[float]) -> np.ndarray:
        """
        Run inference on input features.
        
        Args:
            input_features: List of numerical features matching model's expected input
            
        Returns:
            Model predictions as numpy array
            
        Raises:
            RuntimeError: If model is not loaded
            ValueError: If input shape is incorrect
        """
        if not self.session:
            raise RuntimeError(
                f"ONNX model not loaded. Check if {self.model_path} exists."
            )
        
        # Validate input
        if not isinstance(input_features, (list, np.ndarray)):
            raise ValueError("input_features must be a list or numpy array")
        
        # Convert to numpy array with correct shape
        input_array = np.array([input_features], dtype=np.float32)
        
        # Validate shape
        expected_features = self.get_expected_features()
        if expected_features and input_array.shape[1] != expected_features:
            raise ValueError(
                f"Expected {expected_features} features, got {input_array.shape[1]}"
            )
        
        # Run inference
        try:
            outputs = self.session.run(
                self.output_names,
                {self.input_name: input_array}
            )
            return outputs[0]
            
        except Exception as e:
            raise RuntimeError(f"Inference failed: {str(e)}")
    
    def predict_proba(self, input_features: List[float]) -> np.ndarray:
        """
        Get probability predictions (for classification models).
        
        Returns:
            Probability array for each class
        """
        if not self.session:
            raise RuntimeError("Model not loaded")
        
        input_array = np.array([input_features], dtype=np.float32)
        
        try:
            # For classifiers, second output is usually probabilities
            outputs = self.session.run(
                self.output_names,
                {self.input_name: input_array}
            )
            
            # Return probabilities if available, else return predictions
            return outputs[1] if len(outputs) > 1 else outputs[0]
            
        except Exception as e:
            raise RuntimeError(f"Probability prediction failed: {str(e)}")
    
    def get_expected_features(self) -> int:
        """Get number of expected input features."""
        if self.session:
            input_shape = self.session.get_inputs()[0].shape
            # Shape is typically [None, n_features] or [-1, n_features]
            return input_shape[1] if len(input_shape) > 1 else None
        return None
    
    def get_model_info(self) -> Dict:
        """Get model metadata and performance metrics."""
        return {
            'model_path': str(self.model_path),
            'exists': self.model_path.exists(),
            'loaded': self.session is not None,
            'expected_features': self.get_expected_features(),
            'metadata': self.model_info
        }


# ========================================
# Singleton instances for each model
# ========================================

# Binary classifier: Will student pass? (0/1)
passing_predictor = AIInferenceEngine("passing_predictor.onnx")

# Multi-class classifier: Readiness level (1-4)
readiness_classifier = AIInferenceEngine("readiness_classifier.onnx")

# Regression: Predicted final score (0-100)
performance_forecaster = AIInferenceEngine("performance_forecaster.onnx")


# ========================================
# Helper functions for feature preparation
# ========================================

def prepare_passing_prediction_features(student_data: Dict) -> List[float]:
    """
    Prepare features for passing probability prediction.
    
    Expected features (in order):
    1. avg_assessment_score
    2. total_study_hours
    3. interruption_rate
    4. idle_ratio
    5. consistency_score
    6. focus_quality
    7. score_trend
    8. score_volatility
    9. total_assessments
    10. days_since_last_activity
    11. sessions_per_week
    12. completion_rate
    13. avg_competency_mastery
    14. timeliness
    15. personal_readiness
    """
    features = [
        student_data.get('avg_assessment_score', 0),
        student_data.get('total_study_hours', 0),
        student_data.get('interruption_rate', 0),
        student_data.get('idle_ratio', 0),
        student_data.get('consistency_score', 0.5),
        student_data.get('focus_quality', 0.5),
        student_data.get('score_trend', 0),
        student_data.get('score_volatility', 0),
        student_data.get('total_assessments', 0),
        student_data.get('days_since_last_activity', 0),
        student_data.get('sessions_per_week', 0),
        student_data.get('completion_rate', 0),
        student_data.get('avg_competency_mastery', 0),
        student_data.get('timeliness', 0),
        student_data.get('personal_readiness', 3)
    ]
    
    return features


def prepare_readiness_features(student_data: Dict) -> List[float]:
    """
    Prepare features for readiness classification.
    
    Simpler feature set focused on current state.
    """
    features = [
        student_data.get('avg_assessment_score', 0),
        student_data.get('completion_rate', 0),
        student_data.get('timeliness', 0),
        student_data.get('total_study_hours', 0),
        student_data.get('focus_quality', 0.5),
        student_data.get('consistency_score', 0.5),
        student_data.get('sessions_per_week', 0),
        student_data.get('total_assessments', 0),
        student_data.get('avg_competency_mastery', 0),
        student_data.get('days_since_last_activity', 0)
    ]
    
    return features


def prepare_performance_forecast_features(student_data: Dict) -> List[float]:
    """
    Prepare features for final score prediction.
    
    Most comprehensive feature set.
    """
    features = [
        student_data.get('avg_assessment_score', 0),
        student_data.get('total_study_hours', 0),
        student_data.get('interruption_rate', 0),
        student_data.get('idle_ratio', 0),
        student_data.get('consistency_score', 0.5),
        student_data.get('focus_quality', 0.5),
        student_data.get('score_trend', 0),
        student_data.get('score_volatility', 0),
        student_data.get('total_assessments', 0),
        student_data.get('days_since_last_activity', 0),
        student_data.get('sessions_per_week', 0),
        student_data.get('completion_rate', 0),
        student_data.get('assessments_per_week', 0),
        student_data.get('avg_competency_mastery', 0),
        student_data.get('weakest_competency_mastery', 0),
        student_data.get('mastery_consistency', 0),
        student_data.get('competencies_attempted', 0),
        student_data.get('timeliness', 0),
        student_data.get('personal_readiness', 3),
        student_data.get('preferred_hour', 12),
        student_data.get('time_slot', 1)
    ]
    
    return features


# ========================================
# High-level prediction functions
# ========================================

def predict_passing_probability(student_data: Dict) -> Dict:
    """
    Predict probability of student passing.
    
    Args:
        student_data: Dictionary with student metrics
        
    Returns:
        Dict with prediction results
    """
    try:
        features = prepare_passing_prediction_features(student_data)
        
        # Get probability
        proba = passing_predictor.predict_proba(features)
        probability = float(proba[0][1])  # Probability of class 1 (pass)
        
        # Get binary prediction
        prediction = passing_predictor.predict(features)
        will_pass = bool(prediction[0] == 1)
        
        return {
            'will_pass': will_pass,
            'probability': probability,
            'confidence': 'High' if abs(probability - 0.5) > 0.3 else 'Medium',
            'model': 'passing_predictor'
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'fallback': True,
            'probability': student_data.get('avg_assessment_score', 0) / 100.0
        }


def predict_readiness_level(student_data: Dict) -> Dict:
    """
    Predict student readiness level.
    
    Returns:
        Dict with readiness classification
    """
    try:
        features = prepare_readiness_features(student_data)
        
        # Get prediction (1-4)
        prediction = readiness_classifier.predict(features)
        level = int(prediction[0])
        
        # Get probabilities for all classes
        proba = readiness_classifier.predict_proba(features)
        
        level_names = {1: 'Very Low', 2: 'Low', 3: 'Moderate', 4: 'High'}
        
        return {
            'level': level,
            'level_name': level_names.get(level, 'Unknown'),
            'confidence': float(proba[0][level - 1]),
            'probabilities': {
                level_names[i+1]: float(proba[0][i]) 
                for i in range(len(proba[0]))
            },
            'model': 'readiness_classifier'
        }
        
    except Exception as e:
        # Fallback to student's self-reported readiness
        return {
            'error': str(e),
            'fallback': True,
            'level': student_data.get('personal_readiness', 3)
        }


def predict_final_score(student_data: Dict) -> Dict:
    """
    Predict final exam score.
    
    Returns:
        Dict with score prediction
    """
    try:
        features = prepare_performance_forecast_features(student_data)
        
        # Get predicted score
        prediction = performance_forecaster.predict(features)
        predicted_score = float(prediction[0])
        
        # Clamp to valid range
        predicted_score = max(0, min(100, predicted_score))
        
        # Calculate confidence based on current performance
        current_score = student_data.get('avg_assessment_score', 0)
        confidence = 1 - (abs(predicted_score - current_score) / 100)
        
        return {
            'predicted_score': round(predicted_score, 2),
            'current_score': current_score,
            'expected_change': round(predicted_score - current_score, 2),
            'confidence': round(confidence, 2),
            'model': 'performance_forecaster'
        }
        
    except Exception as e:
        # Fallback to current average
        return {
            'error': str(e),
            'fallback': True,
            'predicted_score': student_data.get('avg_assessment_score', 0)
        }


# ========================================
# Model health check
# ========================================

def check_models_health() -> Dict:
    """
    Check if all models are loaded and ready.
    
    Returns:
        Status of all models
    """
    return {
        'passing_predictor': passing_predictor.get_model_info(),
        'readiness_classifier': readiness_classifier.get_model_info(),
        'performance_forecaster': performance_forecaster.get_model_info(),
        'all_loaded': all([
            passing_predictor.session is not None,
            readiness_classifier.session is not None,
            performance_forecaster.session is not None
        ])
    }