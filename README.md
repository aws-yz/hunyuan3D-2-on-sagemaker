# Hunyuan3D-2 SageMaker 自定义容器部署指南

_[English Version / 英文版本](README_EN.md)_

## 概述

本项目实现了腾讯 Hunyuan3D-2 模型在 Amazon SageMaker 上的自定义容器部署，支持从 2D 图像生成高质量 3D 模型。

## 🎯 核心功能

- **SageMaker 集成**：完全兼容 SageMaker 推理服务
- **异步加载**：后台模型加载，不阻塞服务启动

## 🏗️ 架构组件

### 模型版本对比

| 模型版本        | 参数量 | 特点               | 适用场景                     |
| --------------- | ------ | ------------------ | ---------------------------- |
| Hunyuan3D-2mini | 0.6B   | 轻量快速，形状生成 | 当前部署版本，平衡性能与速度 |
| Hunyuan3D-2     | 1.3B   | 完整纹理合成       | 高质量纹理生成               |
| Hunyuan3D-2.1   | -      | 生产级 PBR 材质    | 专业级材质渲染               |
| Hunyuan3D-2mv   | -      | 多视角优化         | 多角度一致性生成             |

### 性能基准测试

根据官方评测，Hunyuan3D 2.0 在关键指标上领先：

| 指标           | Hunyuan3D 2.0 | 业界最佳 | 优势    |
| -------------- | ------------- | -------- | ------- |
| CMMD (↓)       | 3.193         | 3.218    | ✅ 更好 |
| FID_CLIP (↓)   | 49.165        | 49.744   | ✅ 更好 |
| FID (↓)        | 282.429       | 289.287  | ✅ 更好 |
| CLIP-score (↑) | 0.809         | 0.806    | ✅ 更好 |

### 核心文件

```
├── Dockerfile              # 容器构建配置
├── inference.py            # 推理逻辑（基于官方 api_server.py）
├── serve                   # Flask 服务器入口
├── build_and_deploy.py     # 自动化构建部署脚本
├── test_endpoint.py        # 端点功能测试
├── generate_3d_shape.py    # 基础3D形状生成示例
└── generate_textured_3d.py # 带纹理3D模型生成示例
```

## 🚀 快速部署

### 前提条件

#### AWS 环境配置
```bash
# 1. 安装 AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 2. 配置 AWS 凭证
aws configure
# 输入 Access Key ID、Secret Access Key、Region (建议 us-east-1)
```

#### 必需的 AWS 权限
确保您的 AWS 账户具有以下权限：

**SageMaker 权限**：
- `sagemaker:CreateModel`
- `sagemaker:CreateEndpointConfig`
- `sagemaker:CreateEndpoint`
- `sagemaker:UpdateEndpoint`
- `sagemaker:DescribeEndpoint`
- `sagemaker:DeleteEndpoint`
- `sagemaker:DeleteEndpointConfig`
- `sagemaker:DeleteModel`

**ECR 权限**：
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:BatchGetImage`
- `ecr:CreateRepository`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`

**S3 权限**：
- `s3:CreateBucket`
- `s3:PutObject`
- `s3:GetObject`

**CodeBuild 权限**：
- `codebuild:CreateProject`
- `codebuild:StartBuild`
- `codebuild:BatchGetBuilds`
- `codebuild:BatchGetProjects`
- `codebuild:ListBuilds`
- `codebuild:ListProjects`

**IAM 权限**：
- `iam:GetRole`
- `iam:PassRole` (针对 SageMaker 执行角色)

**CloudWatch Logs 权限**：
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`

#### 资源配额要求
- **GPU 实例配额**：确保 `ml.g5.2xlarge` 实例配额 ≥ 1
- **存储空间**：至少 20GB 可用空间用于 Docker 镜像构建
- **网络**：稳定的网络连接用于下载模型权重（约 10GB）

#### SageMaker 执行角色
创建或确保存在 SageMaker 执行角色：
```bash
# 检查现有角色
aws iam get-role --role-name SageMakerExecutionRole

# 如果不存在，脚本会自动创建
```

### 1. 环境准备

```bash
# 创建虚拟环境
python3 -m venv hunyuan3d-env
source hunyuan3d-env/bin/activate

# 安装依赖
pip install boto3 sagemaker pillow
```

### 2. 一键部署

```bash
python build_and_deploy.py
```

### 3. 功能测试

```bash
# 快速功能测试
python test_endpoint.py

# 生成基础3D形状
python generate_3d_shape.py

# 生成带纹理的 3D 模型
python generate_textured_3d.py
```

## 📊 性能指标

| 配置项   | 规格          | 说明                        |
| -------- | ------------- | --------------------------- |
| 实例类型 | ml.g5.2xlarge | 24GB GPU 内存，适合大型模型 |
| 模型大小 | ~9.7GB        | 包含完整 PyTorch 推理环境   |
| 构建时间 | 8-15 分钟     | CodeBuild 远程构建时间      |
| 端点启动 | 7-10 分钟     | 端点创建到 InService 时间   |
| 模型加载 | 3-8 分钟      | 模型初始化和权重加载时间    |
| 推理速度 | 30-60 秒      | 取决于步数和纹理设置        |

## 🔍 故障排除

### 常见问题

1. **推理错误**

   ```
   zero-size array to reduction operation minimum which has no identity
   ```

   **解决**：检查输入图像格式，确保图像尺寸合理（建议 ≥ 256x256）

2. **模型加载超时**

   ```
   模型加载超时，已重试60次
   ```

   **解决**：检查实例资源，模型加载通常需要 5-10 分钟

3. **OpenGL 错误**

   ```
   libOpenGL.so.0: cannot open shared object file
   ```

   **解决**：确保安装完整的 OpenGL 依赖包

4. **端点配置错误**
   ```
   Could not find endpoint configuration
   ```
   **解决**：使用修复后的 `build_and_deploy.py` 自动处理

### 调试工具

**查看端点日志**：

```bash
aws logs get-log-events \
  --log-group-name /aws/sagemaker/Endpoints/hunyuan3d-custom-endpoint \
  --log-stream-name "AllTraffic/i-xxxxx"
```

**检查端点状态**：

```bash
aws sagemaker describe-endpoint --endpoint-name hunyuan3d-custom-endpoint
```

## 📋 API 参考

### 输入格式

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

### 输出格式

```json
{
  "status": "completed",
  "model_base64": "base64_encoded_glb_file"
}
```

## 🎨 使用示例

### 生成基础 3D 模型

```python
import boto3, json, base64
from PIL import Image
from io import BytesIO

# 创建测试图片
img = Image.new('RGB', (256, 256), color=(255, 0, 0))
buffer = BytesIO()
img.save(buffer, format='PNG')
img_b64 = base64.b64encode(buffer.getvalue()).decode()

# 调用推理
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

# 保存结果
result = json.loads(response['Body'].read().decode())
if result['status'] == 'completed':
    model_data = base64.b64decode(result['model_base64'])
    with open('output.glb', 'wb') as f:
        f.write(model_data)
```

## 🔧 部署要点

### 1. 系统依赖配置

**关键 OpenGL 依赖**：

```dockerfile
RUN apt-get update && apt-get install -y \
    git \
    ninja-build \
    libgl1-mesa-glx \
    libglu1-mesa \
    libopengl0 \          # 核心 OpenGL 库
    libglx0 \             # GLX 扩展
    libxrender1 \         # X11 渲染支持
    libxext6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*
```

### 2. 模型加载策略

**异步加载模式**：

```python
# 后台线程加载模型，避免阻塞服务启动
def load_model_async():
    model_handler.load_models()  # 注意方法名

model_thread = threading.Thread(target=load_model_async)
model_thread.daemon = True
model_thread.start()
```

**状态检查机制**：

```python
if not self.model_loaded:
    return {
        'error': 'Model not loaded yet, please wait',
        'status': 'loading'
    }
```

### 3. 推理参数配置

**基础 3D 生成**：

```json
{
  "image": "base64_encoded_image",
  "texture": false,
  "num_inference_steps": 5,
  "seed": 42,
  "guidance_scale": 7.5
}
```

**带纹理生成**：

```json
{
  "image": "base64_encoded_image",
  "texture": true,
  "num_inference_steps": 8,
  "face_count": 30000
}
```

### 4. 部署流程

- **端点配置管理**：自动创建新配置并更新端点
- **错误恢复机制**：检测损坏状态并自动重建
- **模型版本控制**：每次构建创建新模型定义

```python
# 部署逻辑
def deploy_model(image_uri):
    # 1. 创建新模型
    model.create()

    # 2. 创建新端点配置
    create_endpoint_config(config_name, model_name)

    # 3. 更新或创建端点
    if endpoint_exists:
        update_endpoint(endpoint_name, config_name)
    else:
        create_endpoint(endpoint_name, config_name)
```

## 📚 技术细节

### 基于官方代码实现

- **代码基础**：完全基于官方 api_server.py 重写
- **兼容性**：保持与官方 API 的完全兼容
- **稳定性**：使用官方推荐的模型加载和推理流程

### 模型架构优化

- **Flow-based Diffusion Transformer**：采用可扩展的流式扩散变换器架构
- **FlashVDM**：启用 MC 算法加速推理
- **面数控制**：通过 `face_count` 参数平衡质量和性能
- **内存管理**：推理后自动清理 GPU 缓存

### 部署架构优化

- **异步加载**：后台线程加载模型，不阻塞服务启动
- **错误恢复**：自动检测和修复端点配置问题
- **版本管理**：每次构建自动创建新模型和配置

### 模型组件说明

- **形状生成器**：Hunyuan3D-DiT，基于大规模流式扩散变换器
- **纹理合成器**：Hunyuan3D-Paint，专门用于高质量纹理生成
- **几何对齐**：确保生成的几何体与输入图像正确对齐

## 🔗 相关资源

- [Hunyuan3D-2 官方仓库](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Hunyuan3D-2 论文](https://huggingface.co/papers/2501.12202)
- [Hunyuan3D-2mini 模型](https://huggingface.co/tencent/Hunyuan3D-2mini)
- [Hunyuan3D-2.1 最新版本](https://huggingface.co/tencent/Hunyuan3D-2.1)
- [SageMaker 自定义容器文档](https://docs.aws.amazon.com/sagemaker/latest/dg/docker-containers.html)
- [AWS Deep Learning Containers](https://github.com/aws/deep-learning-containers)

## 🚀 升级路径

### 当前部署状态

- **形状生成**: `tencent/Hunyuan3D-2mini` (subfolder: `hunyuan3d-dit-v2-mini-turbo`)
- **纹理生成**: `tencent/Hunyuan3D-2`
- **架构**: Flow-based Diffusion Transformer

### 可选升级版本

1. **Hunyuan3D-2.1**: 支持生产级 PBR 材质渲染
2. **Hunyuan3D-2mv**: 多视角优化，提供更好的角度一致性
3. **Hunyuan3D-2mini-fast**: 更快的推理速度变体

### 升级注意事项

- 新版本可能需要调整推理参数
- 建议先在测试环境验证兼容性
- 评估新版本的资源需求和性能提升

## 📄 许可证

本项目遵循 Hunyuan3D-2 的原始许可证条款。请参考官方仓库了解详细的许可证信息。

---
