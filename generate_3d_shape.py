#!/usr/bin/env python3
import boto3
import json
import base64
from PIL import Image, ImageDraw
from io import BytesIO

def create_test_object():
    """创建一个有特征的测试图片 - 简单的机器人轮廓"""
    img = Image.new('RGB', (512, 512), color=(255, 255, 255))  # 白色背景
    draw = ImageDraw.Draw(img)
    
    # 绘制简单的机器人轮廓
    # 头部
    draw.rectangle([200, 100, 300, 200], fill=(100, 100, 100), outline=(0, 0, 0), width=3)
    # 眼睛
    draw.ellipse([220, 130, 240, 150], fill=(255, 0, 0))
    draw.ellipse([260, 130, 280, 150], fill=(255, 0, 0))
    # 身体
    draw.rectangle([180, 200, 320, 350], fill=(150, 150, 150), outline=(0, 0, 0), width=3)
    # 手臂
    draw.rectangle([120, 220, 180, 280], fill=(120, 120, 120), outline=(0, 0, 0), width=2)
    draw.rectangle([320, 220, 380, 280], fill=(120, 120, 120), outline=(0, 0, 0), width=2)
    # 腿
    draw.rectangle([200, 350, 240, 450], fill=(120, 120, 120), outline=(0, 0, 0), width=2)
    draw.rectangle([260, 350, 300, 450], fill=(120, 120, 120), outline=(0, 0, 0), width=2)
    
    return img

def generate_and_save_model():
    runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')
    endpoint_name = 'hunyuan3d-custom-endpoint'
    
    # 创建有特征的测试图片
    print("🤖 创建机器人测试图片...")
    img = create_test_object()
    
    # 保存输入图片以供参考
    img.save('input_robot.png')
    print("📸 输入图片已保存到: input_robot.png")
    
    # 转换为base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    # 推理参数
    test_payload = {
        "image": img_b64,
        "texture": False,
        "num_inference_steps": 10,  # 更多步数获得更好质量
        "seed": 42,
        "guidance_scale": 7.5
    }
    
    try:
        print("🚀 开始生成3D机器人模型...")
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(test_payload)
        )
        
        result = json.loads(response['Body'].read().decode())
        
        if result.get('status') == 'completed' and 'model_base64' in result:
            # 解码并保存模型文件
            model_data = base64.b64decode(result['model_base64'])
            
            output_file = 'robot_model.glb'
            with open(output_file, 'wb') as f:
                f.write(model_data)
            
            print(f"✅ 3D机器人模型已保存到: {output_file}")
            print(f"📦 文件大小: {len(model_data)} 字节")
            print(f"🎨 现在应该能看到有特征的3D模型了！")
            
        else:
            print(f"❌ 生成失败: {result}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    generate_and_save_model()