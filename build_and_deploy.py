#!/usr/bin/env python3
"""
使用CodeBuild远程构建和部署Hunyuan3D-2自定义容器（x86架构）
"""

import boto3
import sagemaker
from sagemaker.model import Model
import time
import json
import zipfile
import os
import tempfile
import base64

def format_duration(seconds):
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}分{secs:.0f}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{int(hours)}小时{int(minutes)}分钟"

def create_source_bundle():
    """创建源代码包上传到S3"""
    print("📦 创建源代码包...")
    
    # 创建临时zip文件
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        zip_path = tmp_file.name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加必要文件
        files_to_include = [
            'Dockerfile',
            'serve',
            'inference.py',
            'buildspec.yml'
        ]
        
        for file_name in files_to_include:
            if os.path.exists(file_name):
                zipf.write(file_name)
                print(f"  ✅ 添加文件: {file_name}")
            else:
                print(f"  ❌ 文件不存在: {file_name}")
                return None
    
    # 上传到S3
    s3_client = boto3.client('s3')
    bucket_name = f"hunyuan3d-build-{boto3.client('sts').get_caller_identity()['Account']}"
    s3_key = f"source/hunyuan3d-source-{int(time.time())}.zip"
    
    # 创建S3桶（如果不存在）
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"✅ S3桶已创建: {bucket_name}")
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"✅ S3桶已存在: {bucket_name}")
    except Exception as e:
        print(f"❌ 创建S3桶失败: {e}")
        return None
    
    # 上传源代码
    try:
        s3_client.upload_file(zip_path, bucket_name, s3_key)
        print(f"✅ 源代码已上传: s3://{bucket_name}/{s3_key}")
        os.unlink(zip_path)  # 删除临时文件
        return bucket_name, s3_key
    except Exception as e:
        print(f"❌ 上传源代码失败: {e}")
        return None