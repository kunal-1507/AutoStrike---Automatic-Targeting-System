import cv2
import os
import sys
import glob
import re

video_name = 'video.avi'
img_extension = ".jpg"
# Accept generic names (not only cv_)
name_strip = "cv_"   # used by default but script also accepts any jpg in folder

def numeric_key(fname):
    m = re.search(r'(\d+)', fname)
    return int(m.group(1)) if m else 10**9

def gather_images(input_path):
    if "*" in input_path or "?" in input_path:
        files = glob.glob(input_path)
        return sorted([f for f in files if f.lower().endswith(img_extension)], key=lambda p: numeric_key(os.path.basename(p)))

    if os.path.isfile(input_path):
        return [input_path] if input_path.lower().endswith(img_extension) else []

    if os.path.isdir(input_path):
        all_files = os.listdir(input_path)
        images = [f for f in all_files if f.lower().endswith(img_extension)]
        images_full = [os.path.join(input_path, f) for f in images]
        images_full.sort(key=lambda p: numeric_key(os.path.basename(p)))
        return images_full

    return []

def convert(filepath):
    filepath = os.path.abspath(filepath)

    images = gather_images(filepath)
    if not images:
        print(f"Error: No matching images were found for input: {filepath}")
        print(f"Provide a folder with .jpg images or use a glob pattern like .\\images\\*.jpg")
        sys.exit(1)

    first_frame = None
    for p in images:
        first_frame = cv2.imread(p)
        if first_frame is not None:
            break
        else:
            print(f"Warning: Could not read {p}, trying next...")

    if first_frame is None:
        print("Error: None of the images could be read. Exiting.")
        sys.exit(1)

    height, width = first_frame.shape[:2]

    codec = cv2.VideoWriter_fourcc(*'DIVX')
    out_dir = os.path.dirname(first_frame) if os.path.isfile(filepath) else filepath
    out_path = os.path.join(out_dir, video_name)
    video = cv2.VideoWriter(out_path, codec, 30, (width, height))
    print(f"Writing video -> {out_path}   (frame size: {width}x{height})")

    written = 0
    for p in images:
        img = cv2.imread(p)
        if img is None:
            print(f"Warning: Skipping unreadable image: {p}")
            continue

        if (img.shape[1], img.shape[0]) != (width, height):
            img = cv2.resize(img, (width, height))

        video.write(img)
        written += 1
        if written % 20 == 0:
            print(f"  frames written: {written}")

    video.release()
    cv2.destroyAllWindows()
    print(f"Done. Total frames written: {written}")

if __name__=="__main__":
    if len(sys.argv) < 2:
        print("Usage: python ImageToVid.py <folder_or_image_or_glob>")
        print("Example (folder): python ImageToVid.py .\\images")
        print("Example (glob): python ImageToVid.py .\\images\\*.jpg")
        sys.exit(1)

    convert(sys.argv[1])
