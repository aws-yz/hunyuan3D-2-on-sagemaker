#!/usr/bin/env python3
import boto3
import json
import time
import base64
from PIL import Image
from io import BytesIO

def test_endpoint():
    runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')
    endpoint_name = 'hunyuan3d-custom-endpoint'
    
    # 检查端点状态
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    print("检查端点状态...")
    while True:
        response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        status = response['EndpointStatus']
        print(f"端点状态: {status}")
        
        if status == 'InService':
            print("✅ 端点已就绪，开始测试")
            break
        elif status == 'Failed':
            print("❌ 端点更新失败")
            return
        else:
            print("⏳ 等待端点更新完成...")
            time.sleep(30)
    
    # 创建测试图片并转换为 base64
    print("📸 创建测试图片...")
    img = Image.new('RGB', (256, 256), color=(255, 0, 0))  # 红色正方形
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    # 测试推理
    test_payload = {
        "image": img_b64,
        "texture": False,
        "num_inference_steps": 2,  # 最少步数用于快速测试
        "seed": 42
    }
    
    try:
        print("\n开始推理测试...")
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(test_payload)
        )
        
        result = json.loads(response['Body'].read().decode())
        print("✅ 推理成功!")
        print(f"响应状态: {result.get('status', 'unknown')}")
        
        # 检查响应内容
        if result.get('status') == 'completed':
            print("🎉 3D模型生成成功!")
            if 'model_base64' in result:
                model_size = len(result['model_base64'])
                print(f"📦 生成的3D模型数据大小: {model_size} 字符")
            else:
                print("⚠️ 响应中缺少模型数据")
        elif result.get('status') == 'loading':
            print("⏳ 模型仍在加载中...")
        elif result.get('status') == 'failed':
            print(f"❌ 推理失败: {result.get('error', 'Unknown error')}")
        else:
            print(f"ℹ️ 其他状态: {result}")
            
    except Exception as e:
        print(f"❌ 推理测试失败: {e}")

if __name__ == "__main__":
    test_endpoint()
