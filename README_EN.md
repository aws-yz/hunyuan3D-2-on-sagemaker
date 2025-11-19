# Hunyuan3D-2 SageMaker Custom Container Deployment Guide

_[中文版本 / Chinese Version](README.md)_

## Overview

This project implements the deployment of Tencent's Hunyuan3D-2 model on Amazon SageMaker using custom containers, supporting high-quality 3D model generation from 2D images.

## 🎯 Core Features

- **GLB Format Output**: Compatible with mainstream 3D viewers and editors
- **OpenGL Compatibility Fix**: Resolve PyMeshLab library dependency issues
- **SageMaker Integration**: Fully compatible with SageMaker inference services
- **Asynchronous Loading**: Background model loading without blocking service startup

## 🏗️ Architecture Components

### Model Version Comparison

| Model Version   | Parameters | Features                             | Use Cases                                        |
| --------------- | ---------- | ------------------------------------ | ------------------------------------------------ |
| Hunyuan3D-2mini | 0.6B       | Lightweight & fast, shape generation | Current deployment, balanced performance & speed |
| Hunyuan3D-2     | 1.3B       | Complete texture synthesis           | High-quality texture generation                  |
| Hunyuan3D-2.1   | -          | Production-grade PBR materials       | Professional material rendering                  |
| Hunyuan3D-2mv   | -          | Multi-view optimization              | Multi-angle consistency generation               |

### Performance Benchmarks

According to official evaluations, Hunyuan3D 2.0 leads in key metrics:

| Metric         | Hunyuan3D 2.0 | Industry Best | Advantage |
| -------------- | ------------- | ------------- | --------- |
| CMMD (↓)       | 3.193         | 3.218         | ✅ Better |
| FID_CLIP (↓)   | 49.165        | 49.744        | ✅ Better |
| FID (↓)        | 282.429       | 289.287       | ✅ Better |
| CLIP-score (↑) | 0.809         | 0.806         | ✅ Better |

### Core Files

```
├── Dockerfile              # Container build configuration
├── inference.py            # Inference logic (based on official api_server.py)
├── serve                   # Flask server entry point
├── build_and_deploy.py     # Automated build and deployment script
├── test_endpoint.py        # Endpoint functionality testing
├── generate_3d_shape.py    # Basic 3D shape generation example
└── generate_textured_3d.py # Textured 3D model generation example
```

## 🔧 Deployment Key Points

### 1. System Dependencies Configuration

**Critical OpenGL Dependencies**:

```dockerfile
RUN apt-get update && apt-get install -y \
    git \
    ninja-build \
    libgl1-mesa-glx \
    libglu1-mesa \
    libopengl0 \          # Core OpenGL library
    libglx0 \             # GLX extension
    libxrender1 \         # X11 rendering support
    libxext6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*
```

### 2. Model Loading Strategy

**Asynchronous Loading Mode**:

```python
# Load model in background thread to avoid blocking service startup
def load_model_async():
    model_handler.load_models()  # Note the method name

model_thread = threading.Thread(target=load_model_async)
model_thread.daemon = True
model_thread.start()
```

**Status Check Mechanism**:

```python
if not self.model_loaded:
    return {
        'error': 'Model not loaded yet, please wait',
        'status': 'loading'
    }
```

### 3. Inference Parameter Configuration

**Basic 3D Generation**:

```json
{
  "image": "base64_encoded_image",
  "texture": false,
  "num_inference_steps": 5,
  "seed": 42,
  "guidance_scale": 7.5
}
```

**Textured Generation**:

```json
{
  "image": "base64_encoded_image",
  "texture": true,
  "num_inference_steps": 8,
  "face_count": 30000
}
```

### 4. Deployment Process

- **Endpoint Configuration Management**: Automatically create new configurations and update endpoints
- **Error Recovery Mechanism**: Detect corrupted states and automatically rebuild
- **Model Version Control**: Create new model definitions for each build

```python
# deployment logic
def deploy_model(image_uri):
    # 1. Create new model
    model.create()

    # 2. Create new endpoint configuration
    create_endpoint_config(config_name, model_name)

    # 3. Update or create endpoint
    if endpoint_exists:
        update_endpoint(endpoint_name, config_name)
    else:
        create_endpoint(endpoint_name, config_name)
```

## 🚀 Quick Deployment

### Prerequisites

#### AWS Environment Configuration
```bash
# 1. Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 2. Configure AWS credentials
aws configure
# Enter Access Key ID, Secret Access Key, Region (recommend us-east-1)
```

#### Required AWS Permissions
Ensure your AWS account has the following permissions:

**SageMaker Permissions**:
- `sagemaker:CreateModel`
- `sagemaker:CreateEndpointConfig`
- `sagemaker:CreateEndpoint`
- `sagemaker:UpdateEndpoint`
- `sagemaker:DescribeEndpoint`
- `sagemaker:DeleteEndpoint`
- `sagemaker:DeleteEndpointConfig`
- `sagemaker:DeleteModel`

**ECR Permissions**:
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `ecr:CreateRepository`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`

**CodeBuild Permissions**:
- `codebuild:CreateProject`
- `codebuild:StartBuild`
- `codebuild:BatchGetBuilds`
- `codebuild:BatchGetProjects`
- `codebuild:ListBuilds`
- `codebuild:ListProjects`

**IAM Permissions**:
- `iam:GetRole`
- `iam:PassRole` (for SageMaker execution role)

**CloudWatch Logs Permissions**:
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`

#### Resource Quota Requirements
- **GPU Instance Quota**: Ensure `ml.g5.2xlarge` instance quota ≥ 1
- **Storage Space**: At least 20GB available space for Docker image building
- **Network**: Stable network connection for downloading model weights (~10GB)

#### SageMaker Execution Role
Create or ensure SageMaker execution role exists:
```bash
# Check existing role
aws iam get-role --role-name SageMakerExecutionRole

# If not exists, script will create automatically
```

### 1. Environment Setup

```bash
# Create virtual environment
python3 -m venv hunyuan3d-env
source hunyuan3d-env/bin/activate

# Install dependencies
pip install boto3 sagemaker pillow
```

### 2. One-Click Deployment

```bash
python build_and_deploy.py
```

### 3. Functionality Testing

```bash
# Quick functionality test
python test_endpoint.py

# Generate basic 3D shape
python generate_3d_shape.py

# Generate textured 3D model
python generate_textured_3d.py
```

## 📊 Performance Metrics

| Configuration   | Specification | Description                                |
| --------------- | ------------- | ------------------------------------------ |
| Instance Type   | ml.g5.2xlarge | 24GB GPU memory, suitable for large models |
| Model Size      | ~9.7GB        | Complete PyTorch inference environment     |
| Loading Time    | 5-10 minutes  | Large model initialization time            |
| Inference Speed | 30-60 seconds | Depends on steps and texture settings      |

## 🔍 Troubleshooting

### Common Issues

1. **OpenGL Error**

   ```
   libOpenGL.so.0: cannot open shared object file
   ```

   **Solution**: Ensure complete OpenGL dependency packages are installed

2. **Model Loading Failure**

   ```
   'ModelHandler' object has no attribute 'load_model'
   ```

   **Solution**: Check method name, should be `load_models()`

3. **Endpoint Configuration Error**
   ```
   Could not find endpoint configuration
   ```
   **Solution**: Use the fixed `build_and_deploy.py` for automatic handling

### Debugging Tools

**View Endpoint Logs**:

```bash
aws logs get-log-events \
  --log-group-name /aws/sagemaker/Endpoints/hunyuan3d-custom-endpoint \
  --log-stream-name "AllTraffic/i-xxxxx"
```

**Check Endpoint Status**:

```bash
aws sagemaker describe-endpoint --endpoint-name hunyuan3d-custom-endpoint
```

## 📋 API Reference

### Input Format

```json
{
    "image": "base64_encoded_png_or_jpg",
    "texture": boolean,
    "num_inference_steps": integer,
    "seed": integer,
    "guidance_scale": float,
    "face_count": integer
}
```

### Output Format

```json
{
  "status": "completed",
  "model_base64": "base64_encoded_glb_file"
}
```

## 🎨 Usage Examples

### Generate Basic 3D Model

```python
import boto3, json, base64
from PIL import Image
from io import BytesIO

# Create test image
img = Image.new('RGB', (256, 256), color=(255, 0, 0))
buffer = BytesIO()
img.save(buffer, format='PNG')
img_b64 = base64.b64encode(buffer.getvalue()).decode()

# Call inference
runtime = boto3.client('sagemaker-runtime')
response = runtime.invoke_endpoint(
    EndpointName='hunyuan3d-custom-endpoint',
    ContentType='application/json',
    Body=json.dumps({
        "image": img_b64,
        "texture": False,
        "num_inference_steps": 5
    })
)

# Save result
result = json.loads(response['Body'].read().decode())
if result['status'] == 'completed':
    model_data = base64.b64decode(result['model_base64'])
    with open('output.glb', 'wb') as f:
        f.write(model_data)
```

## 📚 Technical Details

### Based on Official Code Implementation

- **Code Foundation**: Completely rewritten based on official api_server.py
- **Compatibility**: Maintains full compatibility with official API
- **Stability**: Uses officially recommended model loading and inference processes

### Model Architecture Optimization

- **Flow-based Diffusion Transformer**: Scalable flow-based diffusion transformer architecture
- **FlashVDM**: Enable MC algorithm for accelerated inference
- **Face Count Control**: Balance quality and performance through `face_count` parameter
- **Memory Management**: Automatic GPU cache cleanup after inference

### Deployment Architecture Optimization

- **Asynchronous Loading**: Background thread model loading without blocking service startup
- **Error Recovery**: Automatic detection and repair of endpoint configuration issues
- **Version Management**: Automatically create new models and configurations for each build

### Model Component Description

- **Shape Generator**: Hunyuan3D-DiT, based on large-scale flow-based diffusion transformer
- **Texture Synthesizer**: Hunyuan3D-Paint, specialized for high-quality texture generation
- **Geometric Alignment**: Ensures generated geometry properly aligns with input images

## 🔗 Related Resources

- [Hunyuan3D-2 Official Repository](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Hunyuan3D-2 Paper](https://huggingface.co/papers/2501.12202)
- [Hunyuan3D-2mini Model](https://huggingface.co/tencent/Hunyuan3D-2mini)
- [Hunyuan3D-2.1 Latest Version](https://huggingface.co/tencent/Hunyuan3D-2.1)
- [SageMaker Custom Container Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/docker-containers.html)
- [AWS Deep Learning Containers](https://github.com/aws/deep-learning-containers)

## 🚀 Upgrade Path

### Current Deployment Status

- **Shape Generation**: `tencent/Hunyuan3D-2mini` (subfolder: `hunyuan3d-dit-v2-mini-turbo`)
- **Texture Generation**: `tencent/Hunyuan3D-2`
- **Architecture**: Flow-based Diffusion Transformer

### Available Upgrade Versions

1. **Hunyuan3D-2.1**: Production-grade PBR material rendering support
2. **Hunyuan3D-2mv**: Multi-view optimization for better angle consistency
3. **Hunyuan3D-2mini-fast**: Faster inference speed variant

### Upgrade Considerations

- New versions may require inference parameter adjustments
- Recommend testing compatibility in test environment first
- Evaluate resource requirements and performance improvements of new versions

## 📄 License

This project follows the original license terms of Hunyuan3D-2. Please refer to the official repository for detailed license information.

---

**🎉 Deployment Successful! You can now generate high-quality 3D models through SageMaker endpoints!**