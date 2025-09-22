import torch
from transformers import AutoProcessor, AutoModelForVision2Seq
from ultralytics import YOLO
import numpy as np
from PIL import Image
import cv2
import os
import asyncio
import requests

class VisualAnalyzer:
    def __init__(self):
        self.models_initialized = False
        self.scene_description_model = None
        self.scene_processor = None
        self.object_detection_model = None
        self._initialization_lock = asyncio.Lock()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"VisualAnalyzer initialized, will use device: {self.device}")

    async def initialize(self):
        """Initialize the AI models asynchronously"""
        if self.models_initialized:
            print("Models already initialized")
            return

        async with self._initialization_lock:
            if self.models_initialized:  # Double-check after acquiring lock
                print("Models already initialized (double-check)")
                return

            try:
                print("Starting model initialization...")
                # Initialize models in a thread pool to avoid blocking
                await asyncio.to_thread(self._initialize_models)
                self.models_initialized = True
                print(f"Models initialized successfully on device: {self.device}")
            except Exception as e:
                print(f"Error during model initialization: {e}")
                raise

    def _initialize_models(self):
        """Initialize the AI models (called from a thread)"""
        print("Loading BLIP model...")
        # Initialize BLIP for scene description (using a smaller model)
        from transformers import BlipProcessor, BlipForConditionalGeneration
        self.scene_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        self.scene_description_model = (
            BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            .to(self.device)
            .eval()  # Set to evaluation mode
        )
        print("BLIP model loaded successfully")

        print("Loading YOLO model...")
        # Initialize YOLO for object detection
        self.object_detection_model = YOLO('yolov8n.pt')
        print("YOLO model loaded successfully")

    async def analyze_image(self, image_path: str) -> dict:
        """Analyze a single image and return comprehensive results"""
        try:
            # Read image
            image = Image.open(image_path).convert('RGB')
            
            # Get scene description
            description = await self._get_scene_description(image)
            
            # Detect objects
            objects = await self._detect_objects(image_path)
            
            # Get category and action (now sync)
            category = self._categorize_scene(description, objects)
            action = self._detect_action(description, objects)
            
            # Calculate importance (now sync)
            importance = self._calculate_importance(description, objects, category, action)
            
            # Return results as a simple dictionary
            return {
                "description": str(description),
                "objects": [{
                    "class": str(obj["class"]),
                    "confidence": float(obj["confidence"]),
                    "position": [float(x) for x in obj["position"]]
                } for obj in objects],
                "category": str(category),
                "action": str(action),
                "importance_score": float(importance)
            }
        except Exception as e:
            print(f"Error in analyze_image: {e}")
            raise

    async def _get_scene_description(self, image: Image.Image) -> str:
        """Generate natural language description of the scene"""
        try:
            inputs = self.scene_processor(image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                generated_ids = self.scene_description_model.generate(
                    pixel_values=inputs.pixel_values,
                    max_length=50,
                    num_beams=5
                )
            return self.scene_processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        except Exception as e:
            print(f"Error in scene description: {e}")
            raise

    async def _detect_objects(self, image_path):
        """Detect objects in the scene using YOLO"""
        try:
            results = self.object_detection_model(image_path)
            objects = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    objects.append({
                        "class": result.names[int(box.cls[0])],
                        "confidence": float(box.conf[0]),
                        "position": box.xyxy[0].tolist()
                    })
            return objects
        except Exception as e:
            print(f"Error in object detection: {e}")
            raise

    def _categorize_scene(self, description, objects):
        """Categorize the scene based on description and objects"""
        try:
            # Count people
            people_count = sum(1 for obj in objects if obj["class"] in ["person", "man", "woman"])
            
            # Check for specific objects
            has_vehicle = any(obj["class"] in ["car", "truck", "bus", "motorcycle"] for obj in objects)
            has_animal = any(obj["class"] in ["dog", "cat", "bird", "horse"] for obj in objects)
            
            # Determine category based on content
            if people_count > 2:
                return "group scene"
            elif "action" in description.lower() or has_vehicle:
                return "action"
            elif "talking" in description.lower() or "speaking" in description.lower():
                return "dialogue"
            elif "landscape" in description.lower() or "nature" in description.lower():
                return "landscape"
            elif people_count == 1 and "close" in description.lower():
                return "close-up"
            else:
                return "general"
        except Exception as e:
            print(f"Error in scene categorization: {e}")
            raise

    def _detect_action(self, description, objects):
        """Detect the main action or activity in the scene"""
        try:
            action_keywords = {
                "walking": ["walk", "walking", "stroll"],
                "running": ["run", "running", "sprint"],
                "talking": ["talk", "speak", "conversation", "dialogue"],
                "fighting": ["fight", "battle", "combat"],
                "driving": ["drive", "car", "vehicle"],
                "sitting": ["sit", "seated"],
                "standing": ["stand", "standing"]
            }
            
            description_lower = description.lower()
            for action, keywords in action_keywords.items():
                if any(keyword in description_lower for keyword in keywords):
                    return action
            
            return "unknown"
        except Exception as e:
            print(f"Error in action detection: {e}")
            raise

    def _calculate_importance(self, description, objects, category, action):
        """Calculate an importance score for the scene (0-1)"""
        try:
            score = 0.5  # base score
            
            # Adjust based on category
            category_weights = {
                "action": 0.3,
                "dramatic": 0.3,
                "emotional": 0.2,
                "dialogue": 0.1,
                "group scene": 0.2,
                "close-up": 0.1,
                "landscape": -0.1,
                "transition": -0.2
            }
            score += category_weights.get(category, 0)
            
            # Adjust based on number of people
            people_count = sum(1 for obj in objects if obj["class"] in ["person", "man", "woman"])
            score += min(people_count * 0.05, 0.2)  # up to 0.2 for multiple people
            
            # Adjust based on action
            action_weights = {
                "fighting": 0.3,
                "running": 0.2,
                "driving": 0.1,
                "talking": 0.05,
                "sitting": -0.1,
                "standing": -0.05
            }
            score += action_weights.get(action, 0)
            
            # Ensure score is between 0 and 1
            return max(0, min(1, score))
        except Exception as e:
            print(f"Error in importance calculation: {e}")
            raise

    async def _transcribe_audio(self, audio_path: str) -> str:
        """Transkribiere das Audio über den Whisper-Docker-Service."""
        url = "http://whisper:9000/asr"
        with open(audio_path, "rb") as f:
            files = {"audio_file": f}
            response = requests.post(url, files=files)
        response.raise_for_status()
        return response.json().get("text", "")

# Create a singleton instance
visual_analyzer = VisualAnalyzer() 