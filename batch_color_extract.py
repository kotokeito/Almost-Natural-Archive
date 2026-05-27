import py5
import numpy as np
import os

# ================= 配置区域 =================
INPUT_DIR = r"D:\kit\Shen_Nan\2026\graduate\official_version\resource\hc1_original_frame"
OUTPUT_DIR = r"D:\kit\Shen_Nan\2026\graduate\official_version\resource\hc1_green_isolated"
THRESHOLD = 220  # 颜色距离阈值
TARGET_RGB = np.array([0, 255, 0]) # 目标色：纯绿
# ===========================================

def setup():
    py5.size(400, 200)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    global files
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.jpg', '.png'))]
    files.sort()
    print(f"检测到 {len(files)} 张图片，使用 NumPy 加速引擎...")

def draw():
    idx = py5.frame_count - 1
    if idx < len(files):
        process_fast(files[idx])
        py5.background(20, 150, 20)
        py5.text(f"Fast Processing: {idx+1}/{len(files)}", 50, 100)
    else:
        print("全部处理完成！")
        py5.no_loop()
        py5.exit_sketch()

def process_fast(filename):
    img = py5.load_image(os.path.join(INPUT_DIR, filename))
    if img is None: return

    # 1. 将图片载入 NumPy 数组 [高度, 宽度, 4] (RGBA)
    img.load_np_pixels()
    # 提取 RGB 通道 (np_pixels 的通道顺序通常是 ARGB 或 RGBA，py5 默认是 RGBA)
    # 我们只取前三个通道：红、绿、蓝
    pixels_rgb = img.np_pixels[:, :, 1:4] # 这里的索引取决于 py5 内部顺序，通常 1:4 是 RGB
    
    # 2. 向量化计算距离 (所有像素同时计算)
    # dist = sqrt( (r-tr)^2 + (g-tg)^2 + (b-tb)^2 )
    diff = pixels_rgb - TARGET_RGB
    dist_sq = np.sum(diff**2, axis=2)
    dist = np.sqrt(dist_sq)

    # 3. 创建掩码：距离大于阈值的像素 (即非绿色区域)
    mask = dist > THRESHOLD
    #mask = dist < THRESHOLD

    # 4. 计算灰度图
    # 灰度 = 0.299*R + 0.587*G + 0.114*B
    r_chan = pixels_rgb[:, :, 0]
    g_chan = pixels_rgb[:, :, 1]
    b_chan = pixels_rgb[:, :, 2]
    gray = (0.299 * r_chan + 0.587 * g_chan + 0.114 * b_chan).astype(np.uint8)

    # 5. 应用结果：将非绿色区域替换为灰度
    # 我们把灰度值赋回红、绿、蓝三个通道
    img.np_pixels[mask, 1] = gray[mask] # R
    img.np_pixels[mask, 2] = gray[mask] # G
    img.np_pixels[mask, 3] = gray[mask] # B

    # 6. 写回并保存
    img.update_np_pixels()
    img.save(os.path.join(OUTPUT_DIR, filename))

if __name__ == "__main__":
    py5.run_sketch()