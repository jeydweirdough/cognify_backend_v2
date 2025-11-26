import onnxruntime as ort
import numpy as np
import os
from core.config import settings

# Path to your ONNX models (ensure this folder exists in your project)
MODEL_DIR = "ml_models"

class AIInferenceEngine:
    def __init__(self, model_name: str):
        """
        Initializes the ONNX runtime session for a specific model.
        Args:
            model_name: The filename of the .onnx model (e.g., 'readiness_predictor.onnx')
        """
        self.model_path = os.path.join(MODEL_DIR, model_name)
        self.session = None
        
        # Lazy loading: Only load the model if it exists
        if os.path.exists(self.model_path):
            self.session = ort.InferenceSession(self.model_path)
            print(f"✅ Loaded ONNX Model: {model_name}")
        else:
            print(f"⚠️ Warning: Model {model_name} not found at {self.model_path}. Inference will fail.")

    def predict(self, input_features: list) -> list:
        """
        Runs inference on the provided features.
        Args:
            input_features: A list or numpy array of numerical features.
        Returns:
            The prediction result (e.g., class label or regression value).
        """
        if not self.session:
            raise FileNotFoundError("ONNX Model not loaded.")

        # Prepare input dict
        input_name = self.session.get_inputs()[0].name
        
        # Convert to numpy float32 as required by most ONNX models
        data = np.array([input_features], dtype=np.float32)
        
        result = self.session.run(None, {input_name: data})
        return result[0].tolist()

# Singleton instances for specific predictors
# You will drop your trained 'student_readiness.onnx' into /ml_models/ later.
readiness_predictor = AIInferenceEngine("student_readiness.onnx")
performance_forecaster = AIInferenceEngine("performance_forecaster.onnx")