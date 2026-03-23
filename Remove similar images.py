"""
유사 이미지 탐지 및 삭제 스크립트 (pHash 기반)
- 퍼셉추얼 해시(pHash)로 시각적으로 비슷한 이미지를 찾습니다.
- 크기/해상도/압축률이 달라도 같은 사진이면 탐지됩니다.
- 삭제 전 미리보기 목록을 보여주고 확인 후 삭제합니다.
 
설치 필요:
    pip install Pillow imagehash
"""
 
import os
import argparse
from pathlib import Path
from collections import defaultdict
 
try:
    from PIL import Image
    import imagehash
except ImportError:
    print("❌ 필요한 라이브러리가 없습니다. 아래 명령어로 설치해주세요:")
    print("   pip install Pillow imagehash")
    exit(1)
 
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif"}
 
 
def get_image_hash(filepath: str) -> imagehash.ImageHash | None:
    """이미지의 퍼셉추얼 해시를 반환합니다."""
    try:
        with Image.open(filepath) as img:
            return imagehash.phash(img)
    except Exception as e:
        print(f"\n  ⚠️  해시 실패: {filepath} ({e})")
        return None
 
 
def find_similar_images(directory: str, threshold: int = 8, recursive: bool = True) -> list:
    """
    유사 이미지 그룹을 찾아 반환합니다.
    threshold: 해시 차이 허용값 (낮을수록 엄격, 0=완전동일, 10=많이 비슷)
    """
    directory = Path(directory)
    if not directory.exists():
        print(f"❌ 오류: '{directory}' 디렉토리가 존재하지 않습니다.")
        return []
 
    glob_pattern = "**/*" if recursive else "*"
    image_files = [
        f for f in directory.glob(glob_pattern)
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
 
    print(f"🔍 총 {len(image_files)}개의 이미지 파일을 검사합니다...\n")
 
    # 해시 계산
    hashes = []
    for i, filepath in enumerate(image_files, 1):
        print(f"\r  진행: {i}/{len(image_files)} - {filepath.name[:40]:<40}", end="", flush=True)
        h = get_image_hash(str(filepath))
        if h is not None:
            hashes.append((str(filepath), h))
 
    print(f"\n\n  ✅ 해시 계산 완료: {len(hashes)}개\n")
 
    # 유사 이미지 그룹핑 (Union-Find 방식)
    n = len(hashes)
    parent = list(range(n))
 
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
 
    def union(x, y):
        parent[find(x)] = find(y)
 
    print("  🔗 유사도 비교 중...")
    for i in range(n):
        for j in range(i + 1, n):
            diff = hashes[i][1] - hashes[j][1]
            if diff <= threshold:
                union(i, j)
 
    # 그룹 생성
    groups = defaultdict(list)
    for i, (filepath, _) in enumerate(hashes):
        groups[find(i)].append(filepath)
 
    # 2개 이상인 그룹만 반환
    similar_groups = [paths for paths in groups.values() if len(paths) > 1]
    return similar_groups
 
 
def remove_duplicates(groups: list, auto_confirm: bool = False, dry_run: bool = False):
    """각 그룹에서 첫 번째 파일을 유지하고 나머지를 삭제합니다."""
    if not groups:
        print("✅ 유사한 이미지 파일이 없습니다.")
        return
 
    total_groups = len(groups)
    total_to_delete = sum(len(g) - 1 for g in groups)
 
    print(f"{'='*60}")
    print(f"📋 유사 그룹: {total_groups}개 | 삭제 대상: {total_to_delete}개")
    print(f"{'='*60}\n")
 
    files_to_delete = []
 
    for idx, paths in enumerate(groups, 1):
        # 파일 크기 기준으로 정렬 (가장 큰 파일 유지)
        paths_sorted = sorted(paths, key=lambda p: os.path.getsize(p), reverse=True)
        kept = paths_sorted[0]
        to_delete = paths_sorted[1:]
 
        print(f"[그룹 {idx}]")
        print(f"  ✅ 유지: {kept}  ({os.path.getsize(kept)/1024:.1f} KB)")
        for path in to_delete:
            size_kb = os.path.getsize(path) / 1024
            print(f"  🗑️  삭제: {path}  ({size_kb:.1f} KB)")
            files_to_delete.append(path)
        print()
 
    if dry_run:
        print("🔎 [드라이런 모드] 실제 파일은 삭제되지 않았습니다.")
        return
 
    if not auto_confirm:
        answer = input(f"위 {len(files_to_delete)}개 파일을 삭제하시겠습니까? (yes/no): ").strip().lower()
        if answer not in ("yes", "y"):
            print("❌ 삭제가 취소되었습니다.")
            return
 
    deleted_count = 0
    freed_bytes = 0
    for path in files_to_delete:
        try:
            size = os.path.getsize(path)
            os.remove(path)
            freed_bytes += size
            deleted_count += 1
            print(f"  삭제됨: {path}")
        except Exception as e:
            print(f"  ⚠️  삭제 실패: {path} ({e})")
 
    print(f"\n✅ 완료! {deleted_count}개 파일 삭제 | 확보된 용량: {freed_bytes / (1024**2):.2f} MB")
 
 
def main():
    parser = argparse.ArgumentParser(
        description="유사 이미지를 찾아 삭제하는 도구 (pHash 기반)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("directory", help="검사할 디렉토리 경로")
    parser.add_argument(
        "--threshold", type=int, default=8,
        help="유사도 허용 범위 (기본값: 8)\n  0  = 완전히 동일한 파일만\n  5  = 매우 비슷한 사진\n  8  = 비슷한 사진 (권장)\n  15 = 느슨하게 비슷한 사진"
    )
    parser.add_argument("--no-recursive", action="store_true", help="하위 폴더 탐색 안 함")
    parser.add_argument("--auto", action="store_true", help="확인 없이 자동 삭제")
    parser.add_argument("--dry-run", action="store_true", help="삭제 없이 결과만 미리 확인")
 
    args = parser.parse_args()
 
    print(f"\n📁 대상 디렉토리: {args.directory}")
    print(f"🎯 유사도 임계값: {args.threshold} (낮을수록 엄격)")
    print(f"🔁 하위 폴더 탐색: {'아니오' if args.no_recursive else '예'}")
    print(f"🔎 드라이런 모드: {'예' if args.dry_run else '아니오'}\n")
 
    groups = find_similar_images(
        directory=args.directory,
        threshold=args.threshold,
        recursive=not args.no_recursive,
    )
 
    remove_duplicates(
        groups=groups,
        auto_confirm=args.auto,
        dry_run=args.dry_run,
    )
 
 
if __name__ == "__main__":
    main()
