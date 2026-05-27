import cv2
import os
from glob import glob

# =========================
# 可修改参数
# =========================

fps = 30

# 输入文件夹列表
#folders = [
    #r"final_output\water_output\water1",
    #r"final_output\water_output\water2"
    
#]

folders = [
    r"final_output\hc1_output\hc1_output1",#shi
    r"final_output\hc1_output\hc1_output2_2",#xu
    r"resource\hc1_original_frame"
    
    
]

# 输出视频路径
output_path = r"video\edited\hc1\hc1.mp4"

# 帧选择规则
# (开始帧, 结束帧, 使用哪个文件夹)
rules = [
    (1, 300, 0),
    (301, 450, 2),
    (451, 600, 0),
    (601, 930, 1),
    (931, 990, 0),
    (991, 1183, 1),
    (1184, 1264, 2)
]

# =========================
# 读取所有序列帧
# =========================

all_frames = []

for folder in folders:
    frames = sorted(glob(os.path.join(folder, "*")))
    all_frames.append(frames)

# 获取视频尺寸（从第一张图读取）
sample_img = cv2.imread(all_frames[0][0])

height, width, _ = sample_img.shape

# =========================
# 创建视频写入器
# =========================

fourcc = cv2.VideoWriter_fourcc(*'mp4v')

writer = cv2.VideoWriter(
    output_path,
    fourcc,
    fps,
    (width, height)
)

# =========================
# 根据规则写入帧
# =========================

for start, end, folder_idx in rules:

    frame_list = all_frames[folder_idx]

    hold_frames = 2

    for frame_num in range(start, end + 1):

        idx = frame_num - 1

        # 抽帧逻辑
        source_idx = (idx // hold_frames) * hold_frames

        source_idx = min(source_idx, len(frame_list) - 1)

        img_path = frame_list[source_idx]

        img = cv2.imread(img_path)

        writer.write(img)

        print(f"输出帧 {frame_num} -> 使用源帧 {source_idx + 1}")

# =========================
# 结束
# =========================

writer.release()

print("输出完成")