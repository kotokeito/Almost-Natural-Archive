import cv2
import os

def images_to_video(img_dir, output_path, fps=30):
    # 1. 获取所有图片文件（确保排序正确）
    files = sorted([f for f in os.listdir(img_dir) if f.endswith('.png') or f.endswith('.jpg')])
    
    if not files:
        print("文件夹内没有找到图片！")
        return

    # 2. 读取第一张图获取画幅尺寸
    first_img = cv2.imread(os.path.join(img_dir, files[0]))
    height, width, layers = first_img.shape
    size = (width, height)

    # 3. 初始化视频写入对象
    # 'mp4v' 对应 .mp4 格式；如果你想用 H.264，可以尝试 'avc1'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video = cv2.VideoWriter(output_path, fourcc, fps, size)

    print(f"开始合成视频，画幅尺寸: {size}, 帧率: {fps}")

    # 4. 逐帧写入
    for i, filename in enumerate(files):
        img_path = os.path.join(img_dir, filename)
        img = cv2.imread(img_path)
        
        # 确保每一帧尺寸一致
        if (img.shape[1], img.shape[0]) != size:
            img = cv2.resize(img, size)
            
        video.write(img)
        
        if i % 100 == 0:
            print(f"已处理 {i} 帧...")

    video.release()
    print(f"视频合成完毕！保存位置: {output_path}")

# --- 使用设置 ---
input_folder = r"final_output\kite_output\kitedirtdeleted" # 你的序列帧路径
output_name = r"video\kiteori.mp4"      # 输出文件名
images_to_video(input_folder, output_name, fps=30)
