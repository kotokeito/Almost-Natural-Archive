import torch
import os
import cv2
import numpy as np
import torch.nn.functional as F
from cotracker.predictor import CoTrackerPredictor
import warnings

# 屏蔽无用的 Future Warning
warnings.filterwarnings("ignore", category=FutureWarning)

# ================= 配置区 =================
VIDEO_PATH = r"original_video\kite_720p.mp4" 
CHECKPOINT = "./scaled_offline.pth"
SAVE_DIR = "./results"
DATA_SAVE_DIR = r"data_output\kite_data_test"

CHUNK_SECONDS = 3    # 内存不够就调小这个（例如 2 或 3）
SCALE = 0.5          # 1080p 建议 0.5，显存小就 0.3
# ==========================================

def select_points_with_mouse(frame, win_name="Select Points"):
    points = []
    frame_copy = frame.copy()
    print(f">>> [{win_name}] click to add point,Enter confirm,C clear, Q skip and strat tracking")
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([x, y])
            cv2.circle(frame_copy, (x, y), 5, (0, 0, 255), -1)
            cv2.imshow(win_name, frame_copy)

    cv2.namedWindow(win_name)
    cv2.setMouseCallback(win_name, mouse_callback)
    cv2.imshow(win_name, frame_copy)
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == 13: break # Enter
        elif key == ord('c'):
            points.clear()
            frame_copy = frame.copy()
            cv2.imshow(win_name, frame_copy)
        elif key == ord('q'): return []
            
    cv2.destroyWindow(win_name)
    return np.array(points)

def run_tracking_long_video():
    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
    if not os.path.exists(DATA_SAVE_DIR): os.makedirs(DATA_SAVE_DIR)

    print(f"loading: {CHECKPOINT}")
    model = CoTrackerPredictor(checkpoint=CHECKPOINT).cuda()


    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("fail to find the file")
        return

    T = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    FPS = int(cap.get(cv2.CAP_PROP_FPS))
    
    new_h, new_w = int(H * SCALE), int(W * SCALE)
    chunk_size = CHUNK_SECONDS * FPS

    master_tracks = {}
    active_points = [] # [[id, x, y], ...]
    next_id = 0

    print(f"视频分辨率: {W}x{H} -> 缩放后: {new_w}x{new_h}")
    print(f"总帧数: {T}, 分段大小: {chunk_size}")

    # 3. 分段处理循环
    for start_t in range(0, T, chunk_size):
        end_t = min(start_t + chunk_size, T)
        actual_chunk_len = end_t - start_t
        
        # --- 按需读取当前片段 ---
        chunk_frames = []
        for _ in range(actual_chunk_len):
            ret, frame = cap.read()
            if not ret: break
            # 缩放并转为 RGB
            frame_resized = cv2.resize(frame, (new_w, new_h))
            chunk_frames.append(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB))
        
        if not chunk_frames: break
        video_chunk_np = np.stack(chunk_frames) # [chunk_t, h, w, 3]

        # --- 交互选点 (每段开始) ---
        first_frame_bgr = cv2.cvtColor(video_chunk_np[0], cv2.COLOR_RGB2BGR)
        new_pts = select_points_with_mouse(first_frame_bgr, f"Time: {start_t//FPS}s - Add New Points")
        
        for pt in new_pts:
            master_tracks[next_id] = {
                "tracks": [np.array([pt[0], pt[1]])] * start_t,
                "visibility": [False] * start_t
            }
            active_points.append([next_id, pt[0], pt[1]])
            next_id += 1

        if not active_points:
            # 如果没点，也要给 master_tracks 填充空位保持同步
            print(f"跳过片段 {start_t}-{end_t} (无追踪目标)")
            continue

        # --- 执行追踪 ---
        video_tensor = torch.from_numpy(video_chunk_np).permute(0, 3, 1, 2)[None].float().cuda()
        # 构造 Queries
        queries = np.array([[0, p[1], p[2]] for p in active_points])
        queries_torch = torch.from_numpy(queries).float().cuda()[None]

        with torch.no_grad():
            pred_tracks, pred_visibility = model(video_tensor, queries=queries_torch)
        
        # --- 更新数据 ---
        updated_active_points = []
        tracks_np = pred_tracks[0].cpu().numpy()
        vis_np = pred_visibility[0].cpu().numpy()

        for idx, (pid, _, _) in enumerate(active_points):
            master_tracks[pid]["tracks"].extend(list(tracks_np[:, idx]))
            master_tracks[pid]["visibility"].extend(list(vis_np[:, idx]))

            # 如果最后时刻还可见，传给下一段
            if vis_np[-1, idx] > 0.5:
                last_pos = tracks_np[-1, idx]
                updated_active_points.append([pid, last_pos[0], last_pos[1]])
            else:
                print(f"ID:{pid} 消失于第 {end_t} 帧")

        active_points = updated_active_points
        
        # 显存回收
        del video_tensor, video_chunk_np, chunk_frames
        torch.cuda.empty_cache()

    cap.release()

    # 4. 数据对齐与导出
    print("\n正在对齐数据并保存...")
    final_tracks = np.zeros((T, next_id, 2))
    final_visibility = np.zeros((T, next_id), dtype=bool)

    for pid, data in master_tracks.items():
        c = np.array(data["tracks"])[:T]
        v = np.array(data["visibility"])[:T]
        curr_len = len(c)
        final_tracks[:curr_len, pid, :] = c
        final_visibility[:curr_len, pid] = v

    np.save(os.path.join(DATA_SAVE_DIR, "tracks_coords.npy"), final_tracks)
    np.save(os.path.join(DATA_SAVE_DIR, "tracks_visibility.npy"), final_visibility)

    # 5. 渲染最终视频 (第二次读取视频流，避免占用内存)
    print("正在渲染最终视频...")
    save_path = os.path.join(SAVE_DIR, "final_long_video.mp4")
    out = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), float(FPS), (new_w, new_h))
    
    cap_render = cv2.VideoCapture(VIDEO_PATH)
    for t in range(T):
        ret, frame = cap_render.read()
        if not ret: break
        frame = cv2.resize(frame, (new_w, new_h))
        
        for pid in range(next_id):
            if t < len(final_visibility) and final_visibility[t, pid]:
                x, y = final_tracks[t, pid]
                cv2.circle(frame, (int(x), int(y)), 4, (0, 255, 0), -1)
                cv2.putText(frame, str(pid), (int(x)+5, int(y)-5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        out.write(frame)
        if t % 100 == 0: print(f"渲染进度: {t}/{T}")
        
    cap_render.release()
    out.release()
    print(f"\n✨ 全部完成！")
    print(f"坐标: {os.path.abspath(DATA_SAVE_DIR)}")
    print(f"视频: {os.path.abspath(save_path)}")

if __name__ == "__main__":
    run_tracking_long_video()