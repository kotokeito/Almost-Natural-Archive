import cv2
import os

def video_to_frames(video_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    cap = cv2.VideoCapture(video_path)
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        # 直接存为 jpg，体积小，读取快
        cv2.imwrite(f"{output_folder}/frame_{count:04d}.jpg", frame)
        count += 1
    cap.release()
    print("转换完成！")

video_to_frames(r"resource\waterori.MP4", r"resource\wateroriframe")