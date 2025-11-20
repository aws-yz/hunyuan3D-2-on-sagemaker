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

def create_codebuild_project():
    """创建CodeBuild项目"""
    print("🏗️ 创建CodeBuild项目...")
    
    codebuild = boto3.client('codebuild')
    account_id = boto3.client('sts').get_caller_identity()['Account']
    region = 'us-east-1'
    
    project_name = 'hunyuan3d-build'
    
    # 创建CodeBuild服务角色
    iam = boto3.client('iam')
    role_name = 'codebuild-hunyuan3d-service-role'
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='CodeBuild service role for Hunyuan3D'
        )
        
        # 附加必要的策略
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser'
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess'
        )
        
        # 添加访问AWS DLC镜像的权限
        dlc_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage"
                    ],
                    "Resource": "arn:aws:ecr:*:763104351884:repository/*"
                },
                {
                    "Effect": "Allow",
                    "Action": "ecr:GetAuthorizationToken",
                    "Resource": "*"
                }
            ]
        }
        
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='DLCAccessPolicy',
            PolicyDocument=json.dumps(dlc_policy)
        )
        
        print(f"✅ CodeBuild服务角色已创建: {role_name}")
        
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"✅ CodeBuild服务角色已存在: {role_name}")
        
        # 确保DLC访问权限存在
        try:
            dlc_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage"
                        ],
                        "Resource": "arn:aws:ecr:*:763104351884:repository/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "ecr:GetAuthorizationToken",
                        "Resource": "*"
                    }
                ]
            }
            
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName='DLCAccessPolicy',
                PolicyDocument=json.dumps(dlc_policy)
            )
            print("✅ DLC访问权限已更新")
        except Exception as e:
            print(f"⚠️ 更新DLC权限失败: {e}")
            
    except Exception as e:
        print(f"⚠️ 创建服务角色失败: {e}")
    
    service_role = f"arn:aws:iam::{account_id}:role/{role_name}"
    
    project_config = {
        'name': project_name,
        'description': 'Build Hunyuan3D-2 Docker container for x86 architecture',
        'serviceRole': service_role,
        'artifacts': {
            'type': 'NO_ARTIFACTS'
        },
        'environment': {
            'type': 'LINUX_CONTAINER',
            'image': 'aws/codebuild/standard:7.0',
            'computeType': 'BUILD_GENERAL1_LARGE',
            'privilegedMode': True,
            'environmentVariables': [
                {
                    'name': 'AWS_DEFAULT_REGION',
                    'value': region
                },
                {
                    'name': 'AWS_ACCOUNT_ID',
                    'value': account_id
                },
                {
                    'name': 'IMAGE_REPO_NAME',
                    'value': 'hunyuan3d-sagemaker'
                }
            ]
        },
        'source': {
            'type': 'S3',
            'location': f'hunyuan3d-build-{account_id}/source/',  # S3桶路径格式
            'buildspec': 'buildspec.yml'
        }
    }
    
    try:
        codebuild.create_project(**project_config)
        print(f"✅ CodeBuild项目已创建: {project_name}")
    except codebuild.exceptions.ResourceAlreadyExistsException:
        print(f"✅ CodeBuild项目已存在: {project_name}")
    except Exception as e:
        print(f"❌ 创建CodeBuild项目失败: {e}")
        return None
    
    return project_name

def build_image_with_codebuild(project_name, bucket_name, s3_key):
    """使用CodeBuild构建镜像"""
    print("🔨 启动CodeBuild构建...")
    build_start_time = time.time()
    
    codebuild = boto3.client('codebuild')
    account_id = boto3.client('sts').get_caller_identity()['Account']
    region = 'us-east-1'
    
    # 确保ECR仓库存在
    ecr_client = boto3.client('ecr', region_name=region)
    repository_name = 'hunyuan3d-sagemaker'
    
    try:
        ecr_client.create_repository(repositoryName=repository_name)
        print("✅ ECR仓库已创建")
    except ecr_client.exceptions.RepositoryAlreadyExistsException:
        print("✅ ECR仓库已存在")
    
    # 启动构建
    try:
        response = codebuild.start_build(
            projectName=project_name,
            sourceLocationOverride=f"{bucket_name}/{s3_key}"
        )
        
        build_id = response['build']['id']
        print(f"✅ 构建已启动: {build_id}")
        
        # 等待构建完成
        print("⏳ 等待构建完成（这可能需要15-30分钟）...")
        
        while True:
            build_info = codebuild.batch_get_builds(ids=[build_id])['builds'][0]
            status = build_info['buildStatus']
            
            if status == 'SUCCEEDED':
                build_duration = time.time() - build_start_time
                print(f"✅ 构建成功完成！耗时: {format_duration(build_duration)}")
                image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repository_name}:latest"
                return image_uri, build_duration
            elif status == 'FAILED':
                build_duration = time.time() - build_start_time
                print(f"❌ 构建失败，耗时: {format_duration(build_duration)}")
                print(f"失败原因: {build_info.get('statusDetail', 'Unknown')}")
                return None, build_duration
            elif status in ['FAULT', 'STOPPED', 'TIMED_OUT']:
                build_duration = time.time() - build_start_time
                print(f"❌ 构建异常终止: {status}，耗时: {format_duration(build_duration)}")
                return None, build_duration
            
            print(f"  构建状态: {status}")
            time.sleep(30)  # 等待30秒后再检查
            
    except Exception as e:
        build_duration = time.time() - build_start_time
        print(f"❌ 启动构建失败: {e}，耗时: {format_duration(build_duration)}")
        return None, build_duration

def deploy_model(image_uri):
    """部署模型到SageMaker"""
    print("🚀 部署模型到SageMaker...")
    deploy_start_time = time.time()
    
    role = sagemaker.get_execution_role()
    endpoint_name = 'hunyuan3d-custom-endpoint'
    
    # 1. 创建新模型
    print("📋 创建SageMaker模型...")
    model_create_start = time.time()
    
    model_name = f'hunyuan3d-model-{int(time.time())}'
    model = Model(
        image_uri=image_uri,
        role=role,
        name=model_name,
        container_log_level=20,
        enable_network_isolation=False
    )
    
    # 实际创建模型到 SageMaker
    model.create()
    model_create_duration = time.time() - model_create_start
    print(f"✅ 创建新模型: {model_name}，耗时: {format_duration(model_create_duration)}")
    
    # 2. 创建新端点配置
    print("⚙️ 创建端点配置...")
    config_create_start = time.time()
    
    config_name = f'hunyuan3d-config-{int(time.time())}'
    sagemaker_client = boto3.client('sagemaker')
    
    sagemaker_client.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                'VariantName': 'AllTraffic',
                'ModelName': model_name,
                'InitialInstanceCount': 1,
                'InstanceType': 'ml.g5.2xlarge',
                'InitialVariantWeight': 1.0,
                'ModelDataDownloadTimeoutInSeconds': 1800,
                'ContainerStartupHealthCheckTimeoutInSeconds': 600
            }
        ]
    )
    config_create_duration = time.time() - config_create_start
    print(f"✅ 端点配置已创建: {config_name}，耗时: {format_duration(config_create_duration)}")
    
    # 3. 检查端点是否存在并决定更新或创建
    endpoint_operation_start = time.time()
    
    try:
        # 尝试获取端点信息
        endpoint_info = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        print(f"⚠️ 端点已存在: {endpoint_name}")
        
        # 更新端点使用新配置
        print(f"🔄 更新端点使用新模型和配置...")
        try:
            endpoint_update_start = time.time()
            sagemaker_client.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name
            )
            
            # 等待端点更新完成
            print("⏳ 等待端点更新完成...")
            waiter = sagemaker_client.get_waiter('endpoint_in_service')
            waiter.wait(
                EndpointName=endpoint_name,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # 最多等待30分钟
            )
            
            endpoint_update_duration = time.time() - endpoint_update_start
            endpoint_operation_duration = time.time() - endpoint_operation_start
            print(f"✅ 端点已更新到新模型: {endpoint_name}")
            print(f"   更新到InService耗时: {format_duration(endpoint_update_duration)}")
            print(f"   端点操作总耗时: {format_duration(endpoint_operation_duration)}")
            
            total_deploy_duration = time.time() - deploy_start_time
            return True, {
                'model_create': model_create_duration,
                'config_create': config_create_duration,
                'endpoint_update': endpoint_operation_duration,
                'endpoint_to_inservice': endpoint_update_duration,
                'total_deploy': total_deploy_duration
            }
            
        except Exception as update_e:
            print(f"⚠️ 端点更新失败: {update_e}")
            print("🔄 删除损坏的端点并重新创建...")
            
            # 删除损坏的端点
            try:
                sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
                print("⏳ 等待端点删除完成...")
                
                # 等待端点删除完成
                while True:
                    try:
                        sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
                        time.sleep(10)
                    except sagemaker_client.exceptions.ClientError as e:
                        if 'does not exist' in str(e):
                            break
                        raise e
                
                print("✅ 损坏的端点已删除")
                
            except Exception as delete_e:
                endpoint_operation_duration = time.time() - endpoint_operation_start
                total_deploy_duration = time.time() - deploy_start_time
                print(f"❌ 删除端点失败: {delete_e}")
                return None, {
                    'model_create': model_create_duration,
                    'config_create': config_create_duration,
                    'endpoint_operation': endpoint_operation_duration,
                    'total_deploy': total_deploy_duration
                }
            
            # 创建新端点
            try:
                endpoint_create_start = time.time()
                sagemaker_client.create_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=config_name
                )
                
                # 等待端点创建完成
                print("⏳ 等待新端点创建完成...")
                waiter = sagemaker_client.get_waiter('endpoint_in_service')
                waiter.wait(
                    EndpointName=endpoint_name,
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
                )
                
                endpoint_create_duration = time.time() - endpoint_create_start
                endpoint_operation_duration = time.time() - endpoint_operation_start
                print(f"✅ 新端点已创建: {endpoint_name}")
                print(f"   创建到InService耗时: {format_duration(endpoint_create_duration)}")
                print(f"   端点操作总耗时: {format_duration(endpoint_operation_duration)}")
                
                return True, {
                    'model_create': model_create_duration,
                    'config_create': config_create_duration,
                    'endpoint_create': endpoint_operation_duration,
                    'endpoint_to_inservice': endpoint_create_duration,
                    'total_deploy': total_deploy_duration
                }
                
            except Exception as create_e:
                endpoint_operation_duration = time.time() - endpoint_operation_start
                total_deploy_duration = time.time() - deploy_start_time
                print(f"❌ 创建新端点失败: {create_e}")
                return None, {
                    'model_create': model_create_duration,
                    'config_create': config_create_duration,
                    'endpoint_operation': endpoint_operation_duration,
                    'total_deploy': total_deploy_duration
                }
        
    except sagemaker_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and 'Could not find endpoint' in str(e):
            # 端点不存在，创建新端点
            print(f"📍 端点不存在，创建新端点: {endpoint_name}")
            try:
                endpoint_create_start = time.time()
                sagemaker_client.create_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=config_name
                )
                
                # 等待端点创建完成
                print("⏳ 等待端点创建完成...")
                waiter = sagemaker_client.get_waiter('endpoint_in_service')
                waiter.wait(
                    EndpointName=endpoint_name,
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
                )
                
                endpoint_create_duration = time.time() - endpoint_create_start
                endpoint_operation_duration = time.time() - endpoint_operation_start
                total_deploy_duration = time.time() - deploy_start_time
                print(f"✅ 新端点已创建: {endpoint_name}")
                print(f"   创建到InService耗时: {format_duration(endpoint_create_duration)}")
                print(f"   端点操作总耗时: {format_duration(endpoint_operation_duration)}")
                
                return True, {
                    'model_create': model_create_duration,
                    'config_create': config_create_duration,
                    'endpoint_create': endpoint_operation_duration,
                    'endpoint_to_inservice': endpoint_create_duration,
                    'total_deploy': total_deploy_duration
                }
                
            except Exception as deploy_e:
                endpoint_operation_duration = time.time() - endpoint_operation_start
                total_deploy_duration = time.time() - deploy_start_time
                print(f"❌ 创建端点失败: {deploy_e}")
                return None, {
                    'model_create': model_create_duration,
                    'config_create': config_create_duration,
                    'endpoint_operation': endpoint_operation_duration,
                    'total_deploy': total_deploy_duration
                }
        else:
            endpoint_operation_duration = time.time() - endpoint_operation_start
            total_deploy_duration = time.time() - deploy_start_time
            print(f"❌ 检查端点状态失败: {e}")
            return None, {
                'model_create': model_create_duration,
                'config_create': config_create_duration,
                'endpoint_operation': endpoint_operation_duration,
                'total_deploy': total_deploy_duration
            }
    
    except Exception as e:
        endpoint_operation_duration = time.time() - endpoint_operation_start
        total_deploy_duration = time.time() - deploy_start_time
        print(f"❌ 部署过程出错: {e}")
        return None, {
            'model_create': model_create_duration,
            'config_create': config_create_duration,
            'endpoint_operation': endpoint_operation_duration,
            'total_deploy': total_deploy_duration
        }

def create_test_image():
    """创建合理的测试图像"""
    from PIL import Image
    import io
    img = Image.new('RGB', (256, 256), color=(128, 128, 128))
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

def test_endpoint(endpoint_name):
    """测试端点"""
    print("🧪 测试端点...")
    test_start_time = time.time()
    model_loading_start = None
    max_retries = 60
    retry_count = 0
    
    try:
        runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')
        
        test_data = {
            "image": base64.b64encode(create_test_image()).decode(),
            "texture": False,
            "num_inference_steps": 2
        }
        
        while retry_count < max_retries:
            try:
                response = runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(test_data)
                )
                
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    result = json.loads(response['Body'].read().decode())
                    
                    if result.get('status') == 'loading':
                        if model_loading_start is None:
                            model_loading_start = time.time()
                            print("⏳ 模型正在加载中，等待加载完成...")
                        print(f"   模型仍在加载中... ({retry_count + 1}/{max_retries})")
                        time.sleep(10)
                        retry_count += 1
                        continue
                    elif result.get('status') == 'completed':
                        test_duration = time.time() - test_start_time
                        model_loading_duration = time.time() - model_loading_start if model_loading_start else 0
                        
                        print(f"✅ 端点测试成功！")
                        print(f"   总测试耗时: {format_duration(test_duration)}")
                        if model_loading_duration > 0:
                            print(f"   模型加载耗时: {format_duration(model_loading_duration)}")
                        
                        return True, test_duration, model_loading_duration
                    elif result.get('status') == 'failed':
                        error_msg = result.get('error', 'Unknown error')
                        print(f"❌ 推理失败: {error_msg}")
                        if 'zero-size array' in error_msg:
                            print("💡 建议: 检查输入图像格式和推理代码中的数组操作")
                        test_duration = time.time() - test_start_time
                        model_loading_duration = time.time() - model_loading_start if model_loading_start else 0
                        return False, test_duration, model_loading_duration
                    else:
                        test_duration = time.time() - test_start_time
                        model_loading_duration = time.time() - model_loading_start if model_loading_start else 0
                        print(f"❌ 端点返回未知状态: {result}")
                        return False, test_duration, model_loading_duration
                        
            except Exception as e:
                if "Model not loaded yet" in str(e) and retry_count < max_retries:
                    if model_loading_start is None:
                        model_loading_start = time.time()
                        print("⏳ 模型正在加载中，等待加载完成...")
                    print(f"   模型仍在加载中... ({retry_count + 1}/{max_retries})")
                    time.sleep(10)
                    retry_count += 1
                    continue
                else:
                    test_duration = time.time() - test_start_time
                    model_loading_duration = time.time() - model_loading_start if model_loading_start else 0
                    print(f"❌ 端点测试失败: {e}")
                    return False, test_duration, model_loading_duration
        
        test_duration = time.time() - test_start_time
        model_loading_duration = time.time() - model_loading_start if model_loading_start else 0
        print(f"❌ 模型加载超时，已重试{max_retries}次")
        return False, test_duration, model_loading_duration
            
    except Exception as e:
        test_duration = time.time() - test_start_time
        model_loading_duration = 0
        print(f"❌ 端点测试失败: {e}")
        return False, test_duration, model_loading_duration

def main():
    """主函数"""
    print("🚀 使用CodeBuild远程构建Hunyuan3D-2容器（x86架构）...")
    total_start_time = time.time()
    
    # 1. 创建源代码包
    source_info = create_source_bundle()
    if not source_info:
        print("❌ 创建源代码包失败")
        return
    
    bucket_name, s3_key = source_info
    
    # 2. 创建CodeBuild项目
    project_name = create_codebuild_project()
    if not project_name:
        print("❌ 创建CodeBuild项目失败")
        return
    
    # 3. 使用CodeBuild构建镜像
    build_result = build_image_with_codebuild(project_name, bucket_name, s3_key)
    if not build_result[0]:
        print("❌ 镜像构建失败")
        return
    
    image_uri, build_duration = build_result
    
    # 4. 部署模型
    deploy_result = deploy_model(image_uri)
    if not deploy_result[0]:
        print("❌ 模型部署失败")
        return
    
    deploy_success, deploy_timings = deploy_result
    
    # 5. 测试端点
    endpoint_name = 'hunyuan3d-custom-endpoint'
    test_success, test_duration, model_loading_duration = test_endpoint(endpoint_name)
    
    # 6. 输出结果和时间统计
    total_duration = time.time() - total_start_time
    
    print("\n" + "="*60)
    print("⏱️  时间统计报告")
    print("="*60)
    print(f"🔨 Docker镜像构建:     {format_duration(build_duration)}")
    print(f"📋 SageMaker模型创建:  {format_duration(deploy_timings['model_create'])}")
    print(f"⚙️  端点配置创建:       {format_duration(deploy_timings['config_create'])}")
    
    if 'endpoint_update' in deploy_timings:
        print(f"🔄 端点更新总计:       {format_duration(deploy_timings['endpoint_update'])}")
    elif 'endpoint_create' in deploy_timings:
        print(f"🆕 端点创建总计:       {format_duration(deploy_timings['endpoint_create'])}")
    
    if 'endpoint_to_inservice' in deploy_timings:
        print(f"⏰ 端点到InService:    {format_duration(deploy_timings['endpoint_to_inservice'])}")
    
    if model_loading_duration > 0:
        print(f"🔄 模型加载时间:       {format_duration(model_loading_duration)}")
    
    print(f"🧪 端点测试:           {format_duration(test_duration)}")
    print(f"📊 SageMaker部署总计:  {format_duration(deploy_timings['total_deploy'])}")
    print(f"🎯 整体部署总计:       {format_duration(total_duration)}")
    print("="*60)
    
    if test_success:
        print("✅ 远程构建和部署完全成功!")
        print(f"📍 端点名称: {endpoint_name}")
        print(f"🐳 镜像URI: {image_uri}")
        print(f"💻 实例类型: ml.g5.2xlarge (24GB GPU)")
        print(f"🏗️ 构建方式: CodeBuild (x86架构)")
    else:
        print("⚠️ 部署成功但测试失败，请检查端点配置")
        print(f"📍 端点名称: {endpoint_name}")

if __name__ == '__main__':
    main()
