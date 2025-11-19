# 使用AWS Deep Learning Container作为基础镜像 - 使用正确的版本
FROM 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker

# 设置SageMaker环境变量
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"
ENV SAGEMAKER_PROGRAM=serve

# 安装系统依赖 - 添加完整的OpenGL支持
RUN apt-get update && apt-get install -y \
    git \
    ninja-build \
    libgl1-mesa-glx \
    libglu1-mesa \
    libopengl0 \
    libglx0 \
    libxrender1 \
    libxext6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# 克隆代码到/app目录 - 与HyperPod保持一致
WORKDIR /app
RUN git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git .

# 安装依赖 - 使用HyperPod的精简方式
RUN pip3 install -r requirements.txt && pip3 install -e .

# 编译扩展 - 使用HyperPod的相对路径方式
RUN cd hy3dgen/texgen/custom_rasterizer && python3 setup.py install
RUN cd hy3dgen/texgen/differentiable_renderer && python3 setup.py install

# 验证安装
RUN python3 -c "import hy3dgen; from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline; print('✅ hy3dgen modules imported successfully')"

# 安装SageMaker所需的额外依赖
RUN pip3 install flask gunicorn

# 创建SageMaker标准目录
RUN mkdir -p /opt/program /opt/ml/model

# 复制推理代码
COPY serve /opt/program/serve
COPY inference.py /opt/program/inference.py

# 设置权限
RUN chmod +x /opt/program/serve

# 设置Python路径 - 指向/app目录
ENV PYTHONPATH="/app:${PYTHONPATH}"

# 设置工作目录
WORKDIR /opt/program

# 暴露SageMaker标准端口
EXPOSE 8080

# 使用SageMaker标准的ENTRYPOINT格式
ENTRYPOINT ["python3", "serve"]