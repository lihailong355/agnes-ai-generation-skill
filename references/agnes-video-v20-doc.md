# Agnes Video V2.0 API Reference (from agnes-ai.com)

Base host: `https://apihub.agnes-ai.com`

Authentication: `Authorization: Bearer YOUR_API_KEY`

Content type: `application/json`

## Overview

Agnes-Video-V2.0 is a production-oriented video generation model. It supports:
- **Text-to-Video**: Generates videos directly from text prompts
- **Image-to-Video**: Converts a static image into an animated video
- **Multi-Image Video Generation**: Uses multiple reference images to guide video generation
- **Keyframe Animation**: Generates smooth transitions between multiple keyframes
- **Scene Motion Control**: Control subject actions, camera movement, and scene dynamics via prompts
- **Visual Consistency**: Maintain subject, style, and scene consistency between frames
- **Cinematic Output**: Generate high-quality cinematic-style videos
- **Asynchronous API**: Send a task first, then query for the generated result

## Use Cases

| Example | Use Case |
|---|---|
| Short films, character scenes, narrative clips | Storytelling |
| Product ads, campaign videos, promotional content | Marketing Videos |
| Reels, Shorts, TikTok-style videos | Social Media Content |
| Animate portraits, products, characters or scenes | Image Animation |
| Generate product demo videos from text or images | Product Demos |
| Create smooth transitions between different visual states | Keyframe Transitions |
| Generate dynamic visual assets for digital products | Game/App Assets |
| Create AI-generated cinematic scenes and atmospheres | Immersive Content |

## Prerequisites

1. A valid Agnes AI API Key
2. Network access to the Agnes AI API Gateway
3. Confirmed model name: `agnes-video-v2.0`
4. A text prompt prepared for video generation
5. Publicly accessible image URLs if using Image-to-Video, Multi-Image Video, or Keyframe Animation

---

## API Endpoints

### Create Video Task (Recommended)

| Element | Description |
|---|---|
| Endpoint | `https://apihub.agnes-ai.com/v1/videos` |
| Method | POST |
| Content-Type | application/json |
| Authentication | Bearer Token |
| Header | Authorization: Bearer YOUR_API_KEY |

### Query Video Result: Recommended Method (video_id)

After creating a video task, the response will include a `video_id`. Use `video_id` to query the video result.

| Element | Description |
|---|---|
| Endpoint | `https://apihub.agnes-ai.com/agnesapi?video_id=<VIDEO_ID>` |
| Method | GET |
| Authentication | Bearer Token |
| Header | Authorization: Bearer YOUR_API_KEY |

### Query Video Result: Legacy Method (task_id)

The previous task-based query endpoint is still available for backward compatibility.

| Element | Description |
|---|---|
| Endpoint | `https://apihub.agnes-ai.com/v1/videos/{task_id}` |
| Method | GET |
| Authentication | Bearer Token |
| Header | Authorization: Bearer YOUR_API_KEY |

---

## Request Parameters for Creating a Video Task

| Parameter | Type | Required | Description |
|---|---|---|---|
| model | string | Yes | Model name. Use `agnes-video-v2.0` |
| prompt | string | Yes | Textual description of the video content |
| image | string / array | No | Image URL or array of image URLs |
| mode | string | No | Generation mode, such as `ti2vid` or `keyframes` |
| height | integer | No | Video height. Default: `768` |
| width | integer | No | Video width. Default: `1152` |
| num_frames | integer | No | Number of video frames. Must be `≤ 441` and satisfy rule `8n + 1` |
| frame_rate | number | No | Video FPS. Supported range: `1-60` |
| num_inference_steps | integer | No | Number of inference steps |
| seed | integer | No | Random seed for reproducible results |
| negative_prompt | string | No | Negative prompt to describe content to avoid |
| extra_body.image | array | No | Input image URLs for multi-image video or keyframe mode |
| extra_body.mode | string | No | Additional mode configuration, such as `keyframes` |

---

## Create Video Task - Examples

### Example 1: Text-to-Video

```bash
curl -X POST https://apihub.agnes-ai.com/v1/videos \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-video-v2.0",
    "prompt": "A cinematic shot of a cat walking on the beach at sunset, soft ocean waves, warm golden lighting, realistic motion",
    "height": 768,
    "width": 1152,
    "num_frames": 121,
    "frame_rate": 24
  }'
```

### Example 2: Image-to-Video

```bash
curl -X POST https://apihub.agnes-ai.com/v1/videos \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-video-v2.0",
    "prompt": "The woman slowly turns around and looks back at the camera, natural facial expression, cinematic camera movement",
    "image": "https://example.com/image.png",
    "num_frames": 121,
    "frame_rate": 24
  }'
```

### Example 3: Multi-Image Video Generation

```bash
curl -X POST https://apihub.agnes-ai.com/v1/videos \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-video-v2.0",
    "prompt": "Create a smooth transformation scene between the two reference images, cinematic lighting, consistent character identity, natural motion",
    "extra_body": {
      "image": [
        "https://example.com/image1.png",
        "https://example.com/image2.png"
      ]
    },
    "num_frames": 121,
    "frame_rate": 24
  }'
```

### Example 4: Keyframe Animation

```bash
curl -X POST https://apihub.agnes-ai.com/v1/videos \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-video-v2.0",
    "prompt": "Generate a smooth cinematic transition between the keyframes, maintaining visual consistency and natural camera movement",
    "extra_body": {
      "image": [
        "https://example.com/keyframe1.png",
        "https://example.com/keyframe2.png"
      ],
      "mode": "keyframes"
    },
    "num_frames": 121,
    "frame_rate": 24
  }'
```

---

## Response After Creating the Task

After successfully creating a video task, the API returns task information including both `task_id` and `video_id`.

```json
{
  "id": "task_YOUR_TASK_ID",
  "task_id": "task_YOUR_TASK_ID",
  "video_id": "video_YOUR_VIDEO_ID",
  "object": "video",
  "model": "agnes-video-v2.0",
  "status": "queued",
  "progress": 0,
  "created_at": 1780457477,
  "seconds": "10.0",
  "size": "1280x768"
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| id | string | Task ID. Can be used with the legacy query endpoint |
| task_id | string | Task ID. Same function as `id` |
| video_id | string | Video ID. Recommended for querying the video result |
| object | string | Object type, typically `video` |
| model | string | Model used by the current task |
| status | string | Current task status |
| progress | integer | Current task progress percentage |
| created_at | integer | Task creation timestamp |
| seconds | string | Video duration in seconds |
| size | string | Video resolution |

---

## Query Video Result

### Recommended Method: Query with video_id

```bash
curl --location --request GET 'https://apihub.agnes-ai.com/agnesapi?video_id=<VIDEO_ID>' \
  --header 'Authorization: Bearer <API_KEY>'
```

Example:
```bash
curl --location --request GET 'https://apihub.agnes-ai.com/agnesapi?video_id=video_xxxxxx' \
  --header 'Authorization: Bearer <API_KEY>'
```

### Optional Parameter: model_name

When querying the video result, you can also pass `model_name` to explicitly specify the model name.

```bash
curl --location --request GET 'https://apihub.agnes-ai.com/agnesapi?video_id=<VIDEO_ID>&model_name=<MODEL>' \
  --header 'Authorization: Bearer <API_KEY>'
```

Example:
```bash
curl --location --request GET 'https://apihub.agnes-ai.com/agnesapi?video_id=video_xxxxxx&model_name=agnes-video-v2.0' \
  --header 'Authorization: Bearer <API_KEY>'
```

Use `model_name` when:
- You are using an upstream raw video ID
- The model used is not the default `agnes-video-v2.0`
- You want to explicitly specify the model used to query the result

When `model_name` is provided, it takes priority.

### Legacy Method: Query with task_id

```bash
curl --location --request GET 'https://apihub.agnes-ai.com/v1/videos/<TASK_ID>' \
  --header 'Authorization: Bearer <API_KEY>'
```

Example:
```bash
curl --location --request GET 'https://apihub.agnes-ai.com/v1/videos/task_xxxxxx' \
  --header 'Authorization: Bearer <API_KEY>'
```

This method is still supported, but new integrations should use the `video_id` query method.

---

## Result Response

```json
{
  "id": "task_YOUR_TASK_ID",
  "video_id": "video_YOUR_VIDEO_ID",
  "model": "agnes-video-v2.0",
  "object": "video",
  "status": "completed",
  "progress": 100,
  "seconds": "10.0",
  "size": "1280x768",
  "remixed_from_video_id": "https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_xxxxxx.mp4",
  "error": null
}
```

### Result Fields

| Field | Type | Description |
|---|---|---|
| id | string | Task ID |
| video_id | string | Video ID |
| model | string | Model used by the current task |
| object | string | Object type |
| status | string | Task status |
| progress | integer | Task progress percentage |
| seconds | string | Video duration in seconds |
| size | string | Video resolution |
| remixed_from_video_id | string | Final URL of the generated video. Only available when `status` is `completed` |
| error | object / null | Error information returned if the task fails |

---

## Task Status Values

| Status | Description |
|---|---|
| queued | Task is waiting in the queue |
| in_progress | Video is being generated |
| completed | Video has been generated successfully |
| failed | Video generation has failed |

---

## Video Duration Control

Agnes-Video-V2.0 allows controlling video duration via `num_frames` and `frame_rate`.

**Formula:** `seconds = num_frames / frame_rate`

Where:
- `num_frames` is the total number of generated frames
- `frame_rate` is the video frame rate (frames per second)
- `num_frames` must be ≤ 441
- `num_frames` must satisfy the rule `8n + 1`
- `frame_rate` supports values from 1 to 60

### Common Duration Configurations

| Target Duration | Recommended Parameters |
|---|---|
| ~3 seconds | num_frames: 81, frame_rate: 24 |
| ~5 seconds | num_frames: 121, frame_rate: 24 |
| ~10 seconds | num_frames: 241, frame_rate: 24 |
| ~18 seconds | num_frames: 441, frame_rate: 24 |

To generate a longer video, increase `num_frames` or reduce `frame_rate`.
To achieve smoother motion, use a higher `frame_rate` such as 24 or 30. However, with the same `num_frames`, a higher `frame_rate` produces a shorter video.

---

## Recommended Parameters

| Scenario | Recommended Configuration |
|---|---|
| Standard video generation | width: 1152, height: 768, num_frames: 121, frame_rate: 24 |
| Short social media video | num_frames: 81 or 121, frame_rate: 24 |
| Longer video | Increase num_frames or reduce frame_rate |
| Smoother motion | Use frame_rate: 24 or 30 |
| Reproducible results | Set a fixed seed |
| Keyframe transition | Use extra_body.mode: "keyframes" |
| Avoid unwanted content | Use negative_prompt |

---

## Prompt Best Practices

### Text-to-Video Prompt

For text-to-video tasks, describe the subject, action, scene, camera movement, lighting, and visual style.

**Recommended structure:**
```
[Subject] + [Action] + [Scene] + [Camera Movement] + [Lighting] + [Style]
```

**Example:**
```
A young astronaut walking across a red desert planet, dust blowing in the wind, slow cinematic tracking shot, dramatic sunset lighting, realistic sci-fi style
```

### Image-to-Video Prompt

For image-to-video tasks, describe which elements should move and which main elements should remain stable.

**Example:**
```
Animate the character with subtle breathing motion, hair moving gently in the wind, background lights flickering softly, while keeping the face and outfit consistent
```

### Multi-Image Video Prompt

For multi-image video tasks, describe the relationship between the input images and how the scene transition should occur.

**Example:**
```
Use the first image as the starting scene and the second image as the target scene. Create a smooth transformation with consistent lighting, natural motion, and cinematic pacing
```

### Keyframe Animation Prompt

For keyframe animation tasks, clearly describe the transition relationship between the keyframes.

**Example:**
```
Create a smooth transition from the first keyframe to the second keyframe, maintaining character identity, consistent camera angle, and natural motion between scenes
```

---

## Error Codes

| Status Code | Description |
|---|---|
| 400 | Invalid request. Check parameters |
| 401 | Unauthorized. Check API Key |
| 404 | Task or video not found |
| 500 | Server error |
| 503 | Service busy. Try again later |

---

## Pricing

| Current Price | Type | Standard Price |
|---|---|---|
| $0 / second | Video Duration | $0.005 / second |

---

## Notes

- Use `agnes-video-v2.0` as the model name.
- Video generation is asynchronous.
- You must create a video task first, then query the result.
- The task creation response returns both `task_id` and `video_id`.
- New integrations should use `video_id` to query results.
- The previous query endpoint by `task_id` is still available.
- `video_url` (or `remixed_from_video_id`) is only available when `status` is `completed`.
- `num_frames` must be ≤ 441.
- `num_frames` must satisfy the rule `8n + 1`, e.g., `81`, `121`, `161`, `241`, or `441`.
- Text-to-Video tasks only require `model` and `prompt`.
- Image-to-Video tasks require an image URL via `image`.
- Multi-Image Video tasks require multiple image URLs in `extra_body.image`.
- Keyframe Animation requires setting `extra_body.mode` to `keyframes`.

---

## CLI: video-stitch (Local Video Stitching)

The Agnes API generates videos in ~5-second segments. Use the `video-stitch` CLI command to concatenate multiple video URLs into one long video with seamless crossfade transitions.

```bash
python scripts/agnes_api.py video-stitch \
  -i "https://example.com/video1.mp4" \
  -i "https://example.com/video2.mp4" \
  -i "https://example.com/video3.mp4" \
  -o output.mp4 \
  --fade-duration 0.8
```

**Parameters:**

| Parameter | Description |
|---|---|
| `--input-video`, `-i` | Input video URL (repeat for multiple videos, minimum 2) |
| `--output`, `-o` | Output file path (default: `stitched-video.mp4`) |
| `--fade-duration` | Crossfade duration in seconds at each transition (default: 0.8) |
| `--with-audio` | Include audio crossfading (default: True) |
| `--raw` | Print the raw provider response |

**How it works:**
1. Downloads all input videos to a temporary directory
2. Uses ffmpeg `xfade` filter for seamless video crossfade at each transition point
3. Uses ffmpeg `acrossfade` filter for smooth audio crossfade
4. Re-encodes video with libx264 (CRF 18) and audio with AAC 128k
5. Cleans up temporary files

**Response format:**

```json
{
  "type": "video-stitch",
  "status": "completed",
  "output": "stitched-video.mp4",
  "urls": ["stitched-video.mp4"],
  "input_count": 3,
  "duration_seconds": 13.54,
  "transition": "fade",
  "fade_duration": 0.8,
  "segments": [
    {"url": "https://example.com/video1.mp4", "path": "/tmp/.../seg0.mp4"},
    {"url": "https://example.com/video2.mp4", "path": "/tmp/.../seg1.mp4"},
    {"url": "https://example.com/video3.mp4", "path": "/tmp/.../seg2.mp4"}
  ]
}
```

**Tip:** To create a 15+ second video from the API, generate multiple ~5s clips and stitch them together with `video-stitch`. The total duration is: `sum(segment_durations) - (num_segments - 1) × fade_duration`.

---

## Character Consistency & Long Videos (Best Approach)

The most reliable way to achieve both **character consistency** and **seamless long videos** is to generate a single long video using keyframe images, rather than stitching multiple segments. This eliminates all transition artifacts and is faster (1 API call vs multiple).

### Recommended: Keyframe + Long Video (No Stitching Needed)

Use `num_frames=441` (18 seconds) with character reference images as keyframes. The API's built-in Visual Consistency ensures the same characters appear consistently across all frames.

```bash
# 1. Generate character keyframe images (one per character)
python scripts/agnes_api.py image \
  --prompt "A brave 6-year-old boy, short black hair, red t-shirt, blue jeans, full body, front view, detailed character design" \
  --size 1024x1024 --seed 42

python scripts/agnes_api.py image \
  --prompt "A giant fierce tiger, muscular, orange and black stripes, menacing expression, full body" \
  --size 1024x1024 --seed 99

# 2. Generate a single 18-second video with keyframe transition
python scripts/agnes_api.py video \
  --prompt "A boy stands in a grassy field holding a toy rifle. The sky rips open and a giant tiger bursts through. The boy aims his rifle at the tiger as they begin to battle. Cinematic action, dramatic lighting, smooth transition from calm scene to epic battle" \
  --image "url-of-boy.png" \
  --image "url-of-tiger-rift.png" \
  --mode keyframes \
  --num-frames 441 \
  --frame-rate 24 \
  --poll
```

**Advantages over multi-segment stitching:**
- **Zero transition artifacts** — 18s generated as a single continuous video
- **Faster** — 1 API call instead of 3-4 video calls + 1 stitch call
- **Lower cost** — 1 task vs multiple tasks
- **Better consistency** — the API's built-in visual consistency maintains characters throughout

### Alternative: Multi-Segment with Character References

If you need separate scenes (different locations, different actions), use character references + stitching:

1. **Generate character reference images** with fixed `--seed`:

```bash
python scripts/agnes_api.py image \
  --prompt "A brave 6-year-old boy with short black hair, wearing a red t-shirt and blue jeans, full body portrait" \
  --size 1024x1024 --seed 42
```

2. **Generate each video segment** using the same `--character-ref`:

```bash
# Scene 1
python scripts/agnes_api.py video \
  --prompt "The boy stands in a grassy field, looking determined" \
  --character-ref "https://.../boy.png" \
  --poll

# Scene 2 (same character ref!)
python scripts/agnes_api.py video \
  --prompt "The sky above the field rips open, a tiger emerges" \
  --character-ref "https://.../boy.png" \
  --poll
```

3. **Stitch with crossfade** (uses ffmpeg xfade for seamless transitions):

```bash
python scripts/agnes_api.py video-stitch \
  -i "seg1.mp4" -i "seg2.mp4" -i "seg3.mp4" \
  -o final.mp4 --fade-duration 0.8
```

### Duration Options

| Flag | Resulting Frames × FPS | Duration | Use Case |
|---|---|---|---|
| `--duration 3` | 81 × 24 | ~3s | Quick action shots |
| `--duration 5` | 121 × 24 | ~5s | Default (single scene) |
| `--duration 10` | 241 × 24 | ~10s | Single action sequence |
| `--duration 18` | 441 × 24 | ~18s | Full story (no stitching) |

Or set `--num-frames` and `--frame-rate` directly. Valid `num_frames` values: ≤ 441 and `8n + 1` (81, 121, 161, 201, 241, 281, 321, 361, 401, 441).

### Multi-Character Consistency

When multiple characters appear together, pass all their reference images:

```bash
# Generate each character with unique seed
python scripts/agnes_api.py image --prompt "boy..." --seed 42
python scripts/agnes_api.py image --prompt "girl..." --seed 99

# Use both in video — every scene must include ALL present characters
python scripts/agnes_api.py video \
  --prompt "The boy and girl stand together in a field" \
  --character-ref "url-of-boy.png" \
  --character-ref "url-of-girl.png" \
  --poll
```

### Parameters for Character Consistency

| Parameter | Description |
|---|---|
| `--character-ref` | Character reference image URL. Repeat for multiple characters. Must use same refs across segments |
| `--image` | Keyframe/start frame images (used with `--mode keyframes`) |
| `--mode keyframes` | Treats images as keyframes for smooth transition between scenes |
| `--seed` | Fixed seed for reproducible character generation (image command) |
| `--duration` | Target duration (3/5/10/18 seconds, auto-sets num_frames+frame_rate) |
| `--num-frames` | Total frames (≤441, must be 8n+1) |

### Key Principles

- **Best consistency**: Use keyframe mode with character images + `--num-frames 441` (18s single video, no stitching)
- **Same refs always**: Every segment featuring a character must include that character's `--character-ref`
- **Full-body refs**: Generate at 1024x1024 with detailed description including clothing color, hairstyle, accessories
- **Describe relationships**: Prompt should describe all characters and their interaction

---

## Batch Video Pipeline: Story → Video

The `video-batch` command automates the entire video creation pipeline from a story to a seamless stitched video.

### Full Pipeline

```bash
python scripts/agnes_api.py video-batch \
  --story "农夫与蛇" \
  --num-segments 6 \
  --duration 10 \
  --output farmer-snake.mp4
```

**Steps (all automatic):**
1. **Storyboard generation** — calls text API to create a professional storyboard with unique camera angles, distinct actions, and character state tracking
2. **Character reference generation** — generates one reference image per unique character using fixed seeds for reproducibility
3. **Parallel video generation** — submits all segments simultaneously (up to 16 concurrent), polls all tasks in parallel
4. **Download** — downloads all completed videos
5. **Stitch** — uses ffmpeg xfade crossfade for seamless transitions

### Related Commands

| Command | Purpose |
|---|---|
| `video-storyboard` | Generate storyboard JSON from a story |
| `video-download` | Download videos from URLs to local files |
| `video-batch` | Full pipeline: story → storyboard → chars → videos → stitch |
| `video-stitch` | Merge existing video files with crossfade transitions |

### Storyboard JSON Format

Each segment contains:
- `shot`: English description of the visual (unique per segment)
- `action`: What characters are doing
- `camera`: Camera movement (wide shot, close-up, tracking, etc.)
- `mood`: Emotional tone
- `lighting`: Lighting description
- `duration`: Target segment duration
- `characters`: List of character names in this shot
- **Prefer long videos**: 10-18s single video > multiple short videos (better consistency, fewer API calls)
- **Every segment must include ALL character refs** that appear in that scene. Only include refs for characters present in the current scene.
