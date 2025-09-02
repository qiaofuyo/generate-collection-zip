import sys
import pyzipper
import os
import subprocess
from send2trash import send2trash
from tqdm import tqdm

# 获取一个唯一的 zip 文件名，避免与现有文件重名
def get_unique_zip_name(source_folder, zip_count, base_name="收藏", extension=".zip"):
    zip_name = os.path.join(source_folder, f"{base_name}{zip_count}{extension}")
    
    # 如果文件已存在，则递增编号，直到找到一个未存在的文件名
    while os.path.exists(zip_name):
        zip_count += 1
        zip_name = os.path.join(source_folder, f"{base_name}{zip_count}{extension}")
    
    return zip_name, zip_count

# 创建一个新的 ZIP 文件（使用存储方式，不压缩文件内容）
def create_zip(zip_name, password, comment, new_add_zip_count):
    zip_file = pyzipper.AESZipFile(zip_name, 'w', compression=pyzipper.ZIP_STORED, encryption=pyzipper.WZ_AES)  #设置名字，压缩方式，加密方法
    zip_file.setpassword(password.encode())  # 设置密码
    zip_file.comment = comment.encode()  # 设置注释
    new_add_zip_count += 1
    return zip_file, new_add_zip_count

# 获取 zip_file 的路径并删除它
def delete_zip_file(zip_file, new_add_zip_count):
    # 获取压缩包的路径
    zip_path = zip_file.filename  # zip_file.filename 存储的是压缩包的路径
    
    # 关闭压缩包，确保文件没有被占用
    zip_file.close()

    # 删除文件
    if os.path.exists(zip_path):
        os.remove(zip_path)
        new_add_zip_count -=1
        print(f"已删除压缩包：{zip_path}")
    else:
        print(f"压缩包 {zip_path} 不存在，无法删除。")
    return new_add_zip_count

# 测试压缩包的完整性
def test_zip_integrity(folder_path, password="123456"):
    # 遍历文件夹中的所有 zip 文件进行检查
    zip_files = [f for f in os.listdir(folder_path) if f.endswith(".zip")]
    
    for zip_file in zip_files:
        zip_path = os.path.join(folder_path, zip_file)
        
        # 尝试打开 ZIP 文件
        try:
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                zf.setpassword(password.encode())  # 设置解压密码
                corrupted_file = zf.testzip()  # 检查压缩包中的文件是否完好
                if corrupted_file is None:
                    print(f"压缩包 {zip_file} 完整性验证通过。")
                else:
                    print(f"压缩包 {zip_file} 中的文件 {corrupted_file} 损坏！")
                    return False  # 返回 False，表示检测失败
        except pyzipper.BadZipFile:
            print(f"压缩包 {zip_file} 损坏或无法打开！")
            return False  # 返回 False，表示检测失败
        except RuntimeError as e:
            print(f"压缩包 {zip_file} 解压失败，错误：{e}")
            return False  # 返回 False，表示检测失败

        # 如果压缩包没有损坏，进一步验证视频是否能播放（使用 FFmpeg 进行基本验证）
        try:
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                zf.setpassword(password.encode())  # 设置解压密码
                for video in zf.namelist():
                    # 临时解压某个视频文件进行播放验证
                    # temp_folder = os.path.join(current_dir, '..', 'tests', 'temp')
                    # temp_folder = os.path.abspath(temp_folder)
                    temp_folder = os.path.join(folder_path, "temp")
                    os.makedirs(temp_folder, exist_ok=True)  # 确保临时文件夹存在
                    temp_video_path = os.path.join(temp_folder, video)
                    zf.extract(video, temp_folder)  # 临时解压文件到临时文件夹
                    
                    try:
                        # 使用 FFmpeg 检查视频是否可播放
                        # result = subprocess.run(
                        #     ['ffmpeg', '-v', 'error', '-i', temp_video_path],
                        #     # stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        #     stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                        # )
                        result = subprocess.run(
                            ['ffmpeg', '-v', 'error', '-i', temp_video_path, '-c:v', 'copy', '-f', 'null', '-'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE
                            # stdout=subprocess.PIPE, stderr=subprocess.STDOUT  # 完整输出日志参数
                        )
                        # print(result.stdout.decode())  # 打印 FFmpeg 的完整输出日志
                        if result.returncode != 0:
                            print(f"视频 {video} 无法播放，解压文件可能损坏。")
                            os.remove(temp_video_path)  # 删除临时解压的视频文件
                            return False  # 返回 False，表示检测失败
                        else:
                            print(f"视频 {video} 可以正常播放。")
                            os.remove(temp_video_path)  # 删除临时解压的视频文件
                    except Exception as e:
                        print(f"无法检查视频文件 {video}，错误：{e}")
                        os.remove(temp_video_path)  # 删除临时解压的视频文件
                        return False  # 返回 False，表示检测失败
        except Exception as e:
            print(f"无法解压压缩包 {zip_file}，错误：{e}")
            return False  # 如果解压失败，返回 False

    return True  # 所有检查通过，返回 True

def compress_videos(source_folder, base_name, zip_count=1, max_zip_size=1.8*1024**3, max_zip_count=50, max_new_add_zip_count=20, password="123456", comment="123456"):
    # 获取所有 mp4 文件并按修改时间排序（从远到近）
    video_files = [f for f in os.listdir(source_folder) if f.endswith(".mp4")]
    video_files.sort(key=lambda f: os.path.getmtime(os.path.join(source_folder, f)), reverse=False)  # 按修改时间从远到近排序
    
    zip_count = zip_count  # 现有 zip 数量
    new_add_zip_count = 0  # 允许新增的 zip 数量
    current_zip_size = 0  # 当前 zip 包大小
    # zip_name = os.path.join(source_folder, f"收藏{zip_count}.zip")
    zip_name, zip_count = get_unique_zip_name(source_folder, zip_count, base_name)  # 获取唯一的 zip 文件名

    waiting_deleted_files = []
    
    zip_file, new_add_zip_count = create_zip(zip_name, password, comment, new_add_zip_count)
    
    # 使用 tqdm 显示进度条
    for video in tqdm(video_files, desc="压缩视频文件", unit="file"):
        video_path = os.path.join(source_folder, video)
        video_size = os.path.getsize(video_path)

        if video_size > max_zip_size:  # 如果单个视频文件的大小超过 2GB，忽略这个视频文件，继续处理下一个
            print(f"忽略视频文件 {video}，因为它的大小超过了 {max_zip_size}  Byte。")
            continue

        if zip_count > max_zip_count:  # 已有 50 个压缩包，停止
            new_add_zip_count = delete_zip_file(zip_file, new_add_zip_count)
            break

        if new_add_zip_count > max_new_add_zip_count:  # 新增 20 个压缩包，停止
            new_add_zip_count = delete_zip_file(zip_file, new_add_zip_count)
            break

        # 如果当前 ZIP 包的大小超出了最大限制，创建新的 ZIP 包
        if current_zip_size + video_size > max_zip_size:
            zip_file.close()  # 关闭当前的 ZIP 包
            if zip_count > max_zip_count:  # 如果已经达到 50 个压缩包，停止
                new_add_zip_count = delete_zip_file(zip_file, new_add_zip_count)
                break
            zip_count += 1  # 压缩包编号增加
            # zip_name = os.path.join(source_folder, f"收藏{zip_count}.zip")  # 新的压缩包文件名
            zip_name, zip_count = get_unique_zip_name(source_folder, zip_count, base_name)  # 获取唯一的 zip 文件名
            zip_file, new_add_zip_count = create_zip(zip_name, password, comment, new_add_zip_count)  # 创建新的 ZIP 文件
            current_zip_size = 0  # 重置当前压缩包大小
        
        # 添加文件到 ZIP 包
        zip_file.write(video_path, os.path.basename(video_path))
        current_zip_size += video_size
        waiting_deleted_files.append(video_path)
        
    zip_file.close()  # 确保最后一个压缩包被关闭

    print(f"压缩完成，共新增了 {new_add_zip_count} 个压缩包。")

    # 在删除源文件之前进行完整性检查
    # if not test_zip_integrity(source_folder, password):
    #     print("压缩包存在问题，程序已停止，源文件未删除。")
    #     return  # 停止程序，避免删除源文件

    # 删除源文件
    for video in waiting_deleted_files:
        video_path = os.path.join(source_folder, video)
        # os.remove(video_path)
        send2trash(video_path)  # 发送到垃圾箱
    # print("源文件已删除。")
    print("源文件已送入垃圾箱。")

# 运行
# source_folder = '../tests/videos'  # 获取当前脚本的相对路径
current_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前脚本的绝对路径
source_folder = os.path.join(current_dir, '../../', '收藏')  # 构建相对路径
source_folder = os.path.abspath(source_folder)  # 转换为绝对路径
compress_videos(source_folder, base_name="收藏", zip_count=155)

# 测试参数
# source_folder = os.path.join(current_dir, '..', 'tests', 'videos')
# source_folder = os.path.abspath(source_folder)
# compress_videos(source_folder, base_name="收藏", max_zip_size=1024*1024*20, max_new_add_zip_count=5)