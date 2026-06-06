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
