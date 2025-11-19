#!/usr/bin/env python3
"""
SageMaker inference script based on official Hunyuan3D-2 api_server.py
"""
import json
import logging
import os
import tempfile
import time
import base64
from io import BytesIO

import torch
import trimesh
from PIL import Image

from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline, FloaterRemover, DegenerateFaceRemover, FaceReducer
from hy3dgen.texgen import Hunyuan3DPaintPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelHandler:
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {self.device}")
        
        # Initialize models
        self.rembg = None
        self.pipeline = None
        self.pipeline_tex = None
        self.model_loaded = False
        
    def load_models(self):
        """Load models following official api_server.py pattern"""
        try:
            logger.info("Loading background remover...")
            self.rembg = BackgroundRemover()
            
            logger.info("Loading shape generation pipeline...")
            self.pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                'tencent/Hunyuan3D-2mini',
                subfolder='hunyuan3d-dit-v2-mini-turbo',
                use_safetensors=True,
                device=self.device,
            )
            self.pipeline.enable_flashvdm(mc_algo='mc')
            
            logger.info("Loading texture generation pipeline...")
            self.pipeline_tex = Hunyuan3DPaintPipeline.from_pretrained('tencent/Hunyuan3D-2')
            
            self.model_loaded = True
            logger.info("✅ All models loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            self.model_loaded = False
            raise

    def load_image_from_base64(self, image_b64):
        """Load image from base64 string"""
        return Image.open(BytesIO(base64.b64decode(image_b64)))

    @torch.inference_mode()
    def generate_shape(self, image, seed=1234, octree_resolution=128, num_inference_steps=5, guidance_scale=5.0):
        """Generate 3D shape from image following official pattern"""
        try:
            logger.info("Generating 3D shape...")
            
            # Remove background
            image = self.rembg(image)
            
            # Setup generation parameters
            generator = torch.Generator(self.device).manual_seed(seed)
            
            start_time = time.time()
            mesh = self.pipeline(
                image=image,
                generator=generator,
                octree_resolution=octree_resolution,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                mc_algo='mc'
            )[0]
            
            logger.info(f"--- {time.time() - start_time} seconds ---")
            return mesh
            
        except Exception as e:
            logger.error(f"Error generating shape: {str(e)}")
            raise

    @torch.inference_mode()
    def generate_texture(self, mesh, image, max_facenum=40000):
        """Generate texture following official pattern"""
        try:
            logger.info("Generating texture...")
            
            # Apply postprocessors in exact order from official API
            mesh = FloaterRemover()(mesh)
            mesh = DegenerateFaceRemover()(mesh)
            mesh = FaceReducer()(mesh, max_facenum=max_facenum)
            mesh = self.pipeline_tex(mesh, image)
            
            return mesh
            
        except Exception as e:
            logger.error(f"Texture generation failed: {str(e)}")
            logger.info("Returning original mesh without texture")
            return mesh

    def save_mesh(self, mesh, output_path, file_type='glb'):
        """Save mesh to file following official pattern"""
        try:
            with tempfile.NamedTemporaryFile(suffix=f'.{file_type}', delete=False) as temp_file:
                mesh.export(temp_file.name)
                mesh = trimesh.load(temp_file.name)
                mesh.export(output_path)
            
            logger.info(f"Mesh saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error saving mesh: {str(e)}")
            raise

    def model_fn(self, model_dir):
        """SageMaker model loading function"""
        logger.info("Loading models...")
        self.load_models()
        return self

    def input_fn(self, request_body, request_content_type):
        """SageMaker input processing function"""
        if request_content_type == 'application/json':
            input_data = json.loads(request_body)
            return input_data
        else:
            raise ValueError(f"Unsupported content type: {request_content_type}")

    def predict_fn(self, input_data, model):
        """SageMaker prediction function following official generate() pattern"""
        try:
            # Check if model is loaded
            if not self.model_loaded:
                return {
                    'error': 'Model not loaded yet, please wait',
                    'status': 'loading'
                }
            
            # Parse input - support both 'image' and 'text' like official API
            if 'image' in input_data:
                image = self.load_image_from_base64(input_data['image'])
            else:
                raise ValueError("No input image provided")
            
            # Generate shape with official parameters
            mesh = self.generate_shape(
                image=image,
                seed=input_data.get('seed', 1234),
                octree_resolution=input_data.get('octree_resolution', 128),
                num_inference_steps=input_data.get('num_inference_steps', 5),
                guidance_scale=input_data.get('guidance_scale', 5.0)
            )
            
            # Generate texture if requested
            if input_data.get('texture', False):
                mesh = self.generate_texture(
                    mesh, 
                    image, 
                    max_facenum=input_data.get('face_count', 40000)
                )
            
            # Save mesh
            file_type = input_data.get('type', 'glb')
            output_path = f'/tmp/output.{file_type}'
            self.save_mesh(mesh, output_path, file_type)
            
            # Clean up GPU memory
            torch.cuda.empty_cache()
            
            # Return base64 encoded result like official API
            with open(output_path, 'rb') as f:
                mesh_data = base64.b64encode(f.read()).decode()
            
            return {
                'model_base64': mesh_data,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            return {
                'error': str(e),
                'status': 'failed'
            }

    def output_fn(self, prediction, accept):
        """SageMaker output processing function"""
        if accept == 'application/json':
            return json.dumps(prediction), accept
        else:
            raise ValueError(f"Unsupported accept type: {accept}")

# Global model handler instance
model_handler = ModelHandler()

# SageMaker entry points
def model_fn(model_dir):
    return model_handler.model_fn(model_dir)

def input_fn(request_body, request_content_type):
    return model_handler.input_fn(request_body, request_content_type)

def predict_fn(input_data, model):
    return model_handler.predict_fn(input_data, model)

def output_fn(prediction, accept):
    return model_handler.output_fn(prediction, accept)

if __name__ == "__main__":
    # Test locally
    handler = ModelHandler()
    handler.load_models()
    print("Model loaded successfully!")