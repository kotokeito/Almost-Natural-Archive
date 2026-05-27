import cv2
import os
import numpy as np

def pre_process_edges(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    files = sorted([f for f in os.listdir(input_dir) if f.endswith('.jpg')])
    
    for f in files:
        img = cv2.imread(os.path.join(input_dir, f))
        # 1. 转灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 2. 高斯模糊（减少细碎杂质）
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        # 3. Canny 边缘检测 (阈值可以根据你的画面对比度调整)
        edges = cv2.Canny(blurred, 0, 110)
        
        # 4. 关键：转为带透明度的 PNG
        # 创建一个 4 通道的图像 (BGRA)
        h, w = edges.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        # --- 修改部分：局部提取逻辑 ---

        # 创建一个布尔掩码：只有边缘点 且 在指定的 x 轴范围内
        # 这里的 980:1280 是切片范围
        mask = np.zeros_like(edges, dtype=bool)
        mask[:, 0:1920] = (edges[:, 0:1920] > 0)
        
        
        # 将符合条件的点设为白色，其余保持 alpha=0 (透明)
        rgba[mask] = [0, 0, 0, 128]
        preview_gray = (mask.astype(np.uint8)) * 255###
        display_window = cv2.cvtColor(preview_gray, cv2.COLOR_GRAY2BGR)
        # 在窗口画一条红线标记 980 的起始位置，方便你对位
        #v2.line(display_window, (980, 0), (980, 720), (0, 0, 255), 1)
        #cv2.putText(display_window, f"File: {f} | Press 'q' to quit", (10, 30), 
                    #cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Edge Extraction Preview", display_window)
        key = cv2.waitKey(30) 
        
        # 按 'q' 键可以提前退出预览
        if key & 0xFF == ord('q'):
            break

        cv2.imwrite(os.path.join(output_dir, f.replace('.jpg', '.png')), rgba)
    print("边缘预处理完成")

# 使用时
pre_process_edges(r"resource\water1_of1_1080", r"resource\water_edge")