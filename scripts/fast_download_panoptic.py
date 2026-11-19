import concurrent.futures
import os
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

URL = "http://images.cocodataset.org/annotations/panoptic_annotations_trainval2017.zip"
TOTAL_SIZE = 860725834
NUM_WORKERS = 16

CACHE_DIR = Path("d:/CODE/TrainAI/lab/K5-L23-DAY10-NHOM-LABUBU10-Release/data_source/cache")
DEST_FILE = CACHE_DIR / "panoptic_annotations_trainval2017.zip"
TMP_DIR = CACHE_DIR / "chunks_panoptic"

def download_chunk(idx, start, end):
    chunk_path = TMP_DIR / f"chunk_{idx:02d}.tmp"
    expected_len = end - start + 1
    if chunk_path.exists() and chunk_path.stat().st_size == expected_len:
        print(f"Chunk {idx:02d} already complete ({expected_len} bytes)")
        return idx
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Range": f"bytes={start}-{end}"
    }
    
    for attempt in range(6):
        try:
            req = urllib.request.Request(URL, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(chunk_path, "wb") as out:
                shutil.copyfileobj(resp, out, length=512 * 1024)
            if chunk_path.stat().st_size == expected_len:
                print(f"Chunk {idx:02d} done ({expected_len // (1024*1024)} MB)")
                return idx
            else:
                print(f"Chunk {idx:02d} size mismatch: got {chunk_path.stat().st_size}, expected {expected_len}, retrying...")
        except Exception as e:
            print(f"Chunk {idx:02d} attempt {attempt+1} failed: {e}")
            time.sleep(1 + attempt)
    raise RuntimeError(f"Failed to download chunk {idx:02d}")

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    
    if DEST_FILE.exists() and DEST_FILE.stat().st_size == TOTAL_SIZE:
        print("panoptic_annotations_trainval2017.zip already exists and is full size!")
        return

    chunk_size = (TOTAL_SIZE + NUM_WORKERS - 1) // NUM_WORKERS
    tasks = []
    for i in range(NUM_WORKERS):
        start = i * chunk_size
        end = min((i + 1) * chunk_size - 1, TOTAL_SIZE - 1)
        tasks.append((i, start, end))
    
    print(f"Starting 16-thread download for {TOTAL_SIZE // (1024*1024)} MB...")
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(download_chunk, idx, start, end) for idx, start, end in tasks]
        for f in concurrent.futures.as_completed(futures):
            f.result()
            
    print(f"All chunks downloaded in {time.time() - t0:.1f}s! Merging...")
    t1 = time.time()
    with open(DEST_FILE, "wb") as outfile:
        for idx in range(NUM_WORKERS):
            chunk_path = TMP_DIR / f"chunk_{idx:02d}.tmp"
            with open(chunk_path, "rb") as infile:
                shutil.copyfileobj(infile, outfile, length=4 * 1024 * 1024)
            chunk_path.unlink()
            
    try:
        TMP_DIR.rmdir()
    except Exception:
        pass
        
    print(f"Merged in {time.time() - t1:.1f}s! Final size: {DEST_FILE.stat().st_size} bytes")
    print("Testing zip archive validity...")
    with zipfile.ZipFile(DEST_FILE) as z:
        print("Zip test:", z.testzip() or "OK")

if __name__ == "__main__":
    main()
