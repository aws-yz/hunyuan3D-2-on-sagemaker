#!/usr/bin/env python3
import boto3
import json
import base64
from PIL import Image, ImageDraw
from io import BytesIO

def create_colorful_robot():
    """创建一个彩色的机器人图片"""
    img = Image.new('RGB', (512, 512), color=(240, 240, 240))  # 浅灰背景
    draw = ImageDraw.Draw(img)
    
    # 绘制彩色机器人
    # 头部 - 蓝色
    draw.rectangle([200, 100, 300, 200], fill=(70, 130, 180), outline=(0, 0, 0), width=3)
    # 眼睛 - 红色
    draw.ellipse([220, 130, 240, 150], fill=(255, 50, 50))
    draw.ellipse([260, 130, 280, 150], fill=(255, 50, 50))
    # 身体 - 绿色
    draw.rectangle([180, 200, 320, 350], fill=(60, 179, 113), outline=(0, 0, 0), width=3)
    # 手臂 - 橙色
    draw.rectangle([120, 220, 180, 280], fill=(255, 140, 0), outline=(0, 0, 0), width=2)
    draw.rectangle([320, 220, 380, 280], fill=(255, 140, 0), outline=(0, 0, 0), width=2)
    # 腿 - 紫色
    draw.rectangle([200, 350, 240, 450], fill=(147, 112, 219), outline=(0, 0, 0), width=2)
    draw.rectangle([260, 350, 300, 450], fill=(147, 112, 219), outline=(0, 0, 0), width=2)
    
    return img

def generate_textured_model():
    runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')
    endpoint_name = 'hunyuan3d-custom-endpoint'
    
    # 创建彩色机器人图片
    print("🌈 创建彩色机器人图片...")
    img = create_colorful_robot()
    
    # 保存输入图片
    img.save('colorful_robot_input.png')
    print("📸 彩色输入图片已保存到: colorful_robot_input.png")
    
    # 转换为base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    # 启用纹理生成的参数
    test_payload = {
        "image": img_b64,
        "texture": True,  # 🎨 启用纹理生成！
        "num_inference_steps": 8,
        "seed": 42,
        "guidance_scale": 7.5,
        "face_count": 30000  # 控制面数，影响纹理质量
    }
    
    try:
        print("🎨 开始生成带纹理的3D机器人模型...")
        print("⏳ 注意：纹理生成需要更长时间（约1-2分钟）...")
        
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(test_payload)
        )
        
        result = json.loads(response['Body'].read().decode())
        
        if result.get('status') == 'completed' and 'model_base64' in result:
            # 解码并保存模型文件
            model_data = base64.b64decode(result['model_base64'])
            
            output_file = 'textured_robot.glb'
            with open(output_file, 'wb') as f:
                f.write(model_data)
            
            print(f"✅ 带纹理的3D机器人已保存到: {output_file}")
            print(f"📦 文件大小: {len(model_data)} 字节")
            print(f"🎨 现在应该能看到彩色的3D模型了！")
            
        else:
            print(f"❌ 生成失败: {result}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    generate_textured_model()