"""Quick test: upload local video → publish as Instagram Reel.

Bypasses the full agent pipeline — directly calls upload_blob + InstagramService.
"""

import asyncio
import sys
from pathlib import Path

# Ensure the insta_agent package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "insta_agent"))

from shared.config.settings import settings
from shared.services.blob_storage_service import upload_blob
from shared.services.instagram_service import InstagramService


VIDEO_PATH = Path(__file__).resolve().parent / "videos" / "1.mp4"
CAPTION = (
    "A golden retriever playing happily in snow ❄️🐕\n"
    "\n"
    "#goldenretriever #dogsofinstagram #snowday #puppylove #happydog"
)


async def main():
    # -- Step 1: Upload to Azure Blob Storage --
    print(f"[1/3] Uploading {VIDEO_PATH.name} to Blob Storage...")
    blob_info = await upload_blob(VIDEO_PATH)
    blob_url = blob_info["blob_url"]
    print(f"  ✅ Uploaded → {blob_url}")
    print(f"  Size: {blob_info['file_size_bytes'] / 1024 / 1024:.1f} MB")

    # -- Step 2: Create Instagram Reel container --
    print(f"\n[2/3] Creating Reel container on Instagram...")
    svc = InstagramService()  # uses default account (oreo)
    container_id = await svc.create_video_container(blob_url, CAPTION)
    print(f"  ✅ Container created: {container_id}")

    # -- Step 3: Wait for processing, then publish --
    print(f"\n[3/3] Waiting for Instagram to process the video...")
    for attempt in range(20):  # up to 10 minutes
        await asyncio.sleep(30)
        status = await svc.check_container_status(container_id)
        status_code = status.get("status_code", "UNKNOWN")
        print(f"  Poll {attempt + 1}/20: {status_code}")

        if status_code == "FINISHED":
            media_id = await svc.publish_container(container_id)
            print(f"\n  🎉 Published! Media ID: {media_id}")
            print(f"  📱 Check your Instagram: https://www.instagram.com/p/{media_id}/")
            return

        if status_code == "ERROR":
            print(f"\n  ❌ Processing failed: {status}")
            return

    print("\n  ⏰ Timed out after 10 minutes of waiting.")


if __name__ == "__main__":
    asyncio.run(main())
