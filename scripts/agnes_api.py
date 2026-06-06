#!/usr/bin/env python3
"""Small CLI for Agnes AI text, image, and video generation APIs."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


BASE_URL = "https://apihub.agnes-ai.com"
TEXT_MODEL = "agnes-2.0-flash"
IMAGE_MODEL = "agnes-image-2.1-flash"
VIDEO_MODEL = "agnes-video-v2.0"
SIZE_RE = re.compile(r"^[1-9]\d*x[1-9]\d*$")


def get_api_key() -> str:
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit(
        "Missing API key. Set AGNES_API_KEY, AGNES_API_TOKEN, or APIHUB_AGNES_API_KEY."
    )


def request_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout_val: int | None = None, max_retries: int = 3) -> dict[str, Any]:
    if timeout_val is None:
        timeout_val = 300
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            BASE_URL + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {get_api_key()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_val) as resp:
                text = resp.read().decode("utf-8")
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            # HTTP errors don't retry, they're client/server errors
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"HTTP {exc.code} from {path}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            if attempt < max_retries:
                print(f"Request failed for {path} (attempt {attempt}/{max_retries}): {exc}. Retrying...", file=sys.stderr)
                time.sleep(min(2 ** attempt, 10))
                continue
            raise SystemExit(f"Request failed for {path} after {max_retries} retries: {exc}") from exc


def request_text(method: str, path: str, payload: dict[str, Any] | None = None) -> str:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {path}: {exc}") from exc


def stream_summary(payload: dict[str, Any]) -> dict[str, Any]:
    raw = request_text("POST", "/v1/chat/completions", payload)
    event_count = 0
    done = False
    content_parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            done = True
        elif data:
            event_count += 1
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            try:
                delta = event["choices"][0].get("delta", {})
            except (KeyError, IndexError, TypeError, AttributeError):
                continue
            content = delta.get("content")
            if isinstance(content, str):
                content_parts.append(content)
    return {
        "type": "text-stream",
        "content": "".join(content_parts) or None,
        "events": event_count,
        "done": done,
        "raw_prefix": raw[:200],
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_json_arg(name: str, value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for {name}: {exc.msg} at position {exc.pos}") from exc


def needs_english_translation(prompt: str) -> bool:
    return any(ord(ch) > 127 for ch in prompt)


def translate_prompt_to_english(prompt: str) -> str:
    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Translate the user's image/video generation prompt into fluent English. "
                    "Preserve all concrete visual details, style words, camera motion, lighting, "
                    "composition constraints, and negative instructions. Return only the English prompt."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 800,
    }
    data = request_json("POST", "/v1/chat/completions", payload)
    try:
        translated = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Prompt translation failed: {json.dumps(data, ensure_ascii=False)}") from exc
    if not translated:
        raise SystemExit("Prompt translation failed: empty translated prompt")
    return translated


def prepare_generation_prompt(prompt: str, translate: bool = True) -> tuple[str, str | None]:
    if translate and needs_english_translation(prompt):
        translated = translate_prompt_to_english(prompt)
        return translated, translated
    return prompt, None


def extract_text_content(data: dict[str, Any]) -> str | None:
    try:
        content = data["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return content if isinstance(content, str) else None


def output_result(
    result_type: str,
    raw: dict[str, Any],
    *,
    prompt_used: str | None = None,
    translated_prompt: str | None = None,
    urls: list[str] | None = None,
    status: str | None = None,
    next_steps: list[str] | None = None,
    raw_only: bool = False,
) -> None:
    if raw_only:
        print_json(raw)
        return
    summary: dict[str, Any] = {"type": result_type}
    if status:
        summary["status"] = status
    if urls:
        summary["urls"] = urls
    if prompt_used:
        summary["prompt_used"] = prompt_used
    if translated_prompt:
        summary["translated_prompt"] = translated_prompt
    if next_steps:
        summary["next_steps"] = next_steps
    summary["raw"] = raw
    print_json(summary)


def extract_image_urls(data: dict[str, Any]) -> list[str]:
    urls = []
    if isinstance(data.get("url"), str):
        url = data["url"]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        urls.append(url)
    if isinstance(data.get("image_url"), str):
        url = data["image_url"]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        urls.append(url)
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        url = item[key]
                        if not url.startswith(("http://", "https://")):
                            url = "https://" + url
                        urls.append(url)
    return urls


def extract_video_urls(data: dict[str, Any]) -> list[str]:
    urls = []
    for key in ("remixed_from_video_id", "video_url", "url"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                urls.extend(extract_video_urls(item))
    return list(dict.fromkeys(urls))


def validate_size(value: str | None, name: str = "size") -> None:
    if value and not SIZE_RE.match(value):
        raise SystemExit(f"Invalid {name}: {value}. Expected WIDTHxHEIGHT, for example 1024x768.")


def validate_video_args(args: argparse.Namespace) -> None:
    if args.num_frames is not None:
        if args.num_frames > 441 or (args.num_frames - 1) % 8 != 0:
            raise SystemExit("Invalid --num-frames: must be <= 441 and satisfy 8n + 1, for example 81 or 121.")
    if args.frame_rate is not None and not (1 <= args.frame_rate <= 60):
        raise SystemExit("Invalid --frame-rate: supported range is 1-60.")
    for name in ("height", "width"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise SystemExit(f"Invalid --{name.replace('_', '-')}: must be a positive integer.")


def cmd_text(args: argparse.Namespace) -> None:
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    payload: dict[str, Any] = {
        "model": TEXT_MODEL,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    if args.top_p is not None:
        payload["top_p"] = args.top_p
    if args.stream:
        payload["stream"] = True
    if args.tools_json:
        payload["tools"] = parse_json_arg("--tools-json", args.tools_json)
    if args.tool_choice_json:
        payload["tool_choice"] = parse_json_arg("--tool-choice-json", args.tool_choice_json)
    if args.stream:
        print_json(stream_summary(payload))
    else:
        data = request_json("POST", "/v1/chat/completions", payload)
        content = extract_text_content(data)
        wrapped = {
            "type": "text",
            "content": content,
            "raw": data,
        }
        print_json(data if args.raw else wrapped)


def cmd_image(args: argparse.Namespace) -> None:
    validate_size(args.size)
    prompt, translated_prompt = prepare_generation_prompt(args.prompt, not args.no_translate_prompt)
    payload: dict[str, Any] = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
    }
    if args.size:
        payload["size"] = args.size
    if args.seed is not None:
        payload["seed"] = args.seed
    extra: dict[str, Any] = {"response_format": "url"}
    if args.image:
        extra["image"] = args.image
    if extra:
        payload["extra_body"] = extra
    data = request_json("POST", "/v1/images/generations", payload)
    urls = extract_image_urls(data)
    output_result(
        "image-to-image" if args.image else "text-to-image",
        data,
        prompt_used=prompt,
        translated_prompt=translated_prompt,
        urls=urls,
        raw_only=args.raw,
    )


def video_payload(args: argparse.Namespace) -> dict[str, Any]:
    validate_video_args(args)
    prompt, translated_prompt = prepare_generation_prompt(args.prompt, not args.no_translate_prompt)
    args._prompt_used = prompt
    args._translated_prompt = translated_prompt
    payload: dict[str, Any] = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
    }

    # Auto-set num_frames and frame_rate from --duration
    if args.duration:
        duration_map = {
            3: (81, 24),
            5: (121, 24),
            10: (241, 24),
            18: (441, 24),
        }
        if args.duration in duration_map:
            nf, fr = duration_map[args.duration]
        else:
            # Fallback: calculate num_frames = duration * frame_rate, rounded to 8n+1
            fr = args.frame_rate if args.frame_rate else 24
            nf = round(args.duration * fr / 8) * 8 + 1
            if nf > 441:
                nf = 441
            if nf < 1:
                nf = 1
        if args.num_frames is None:
            args.num_frames = nf
        if args.frame_rate is None:
            args.frame_rate = fr

    for name in (
        "height",
        "width",
        "num_frames",
        "frame_rate",
        "num_inference_steps",
        "seed",
        "negative_prompt",
    ):
        value = getattr(args, name)
        if value is not None:
            payload[name] = value
    if args.mode:
        payload["mode"] = args.mode
    if args.character_ref:
        # Character reference(s): image(s) that anchor character appearance in video
        # Single ref = image-to-video. Multiple refs = multi-image (each ref = one character)
        # If --mode keyframes is set: treats refs as keyframes for smooth scene transitions
        # If no mode set: image-to-video mode (first ref = starting frame, others = visual guidance)
        all_images = list(args.character_ref)
        if len(all_images) == 1 and not args.image:
            payload["image"] = all_images[0]
        else:
            if args.image:
                all_images.extend(args.image)
            payload["extra_body"] = {"image": all_images}
        # Set mode: keyframes if explicit, otherwise ti2vid
        if not args.mode:
            payload["mode"] = "ti2vid"
        elif args.mode == "keyframes":
            if "extra_body" not in payload:
                payload["extra_body"] = {}
            payload["extra_body"]["mode"] = "keyframes"
    elif args.image:
        if len(args.image) == 1:
            payload["image"] = args.image[0]
        else:
            payload["extra_body"] = {"image": args.image}
            if args.mode:
                payload["extra_body"]["mode"] = args.mode
    return payload


def poll_video(task_id: str, video_id: str | None, timeout: int, interval: int) -> dict[str, Any]:
    """Poll for video completion. Use V2.0 /agnesapi endpoint by default for reliability."""
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    status_interval = max(5, interval // 3)  # print status more frequently than full request
    last_status_print = 0
    while time.time() < deadline:
        elapsed = time.time() - deadline + timeout
        if video_id:
            # V2.0 recommended endpoint
            url = f"/agnesapi?video_id={video_id}"
            last = request_json("GET", url, timeout_val=min(120, timeout - elapsed))
        else:
            # Legacy endpoint
            last = request_json("GET", f"/v1/videos/{task_id}", timeout_val=min(120, timeout - elapsed))
        if last.get("error") and not last.get("remixed_from_video_id"):
            raise SystemExit(f"Video task {task_id or video_id} returned error: {json.dumps(last, ensure_ascii=False)}")
        status = str(last.get("status", "")).lower()
        progress = last.get("progress")
        now = time.time()
        if status and (now - last_status_print) >= status_interval:
            print(f"video {task_id or video_id}: status={status} progress={progress} (elapsed={int(elapsed)}s)", file=sys.stderr)
            last_status_print = now
        if status in {"completed", "failed"}:
            return last
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        sleep_time = min(interval, remaining)
        time.sleep(sleep_time)
    raise SystemExit(f"Timed out waiting for video task {task_id or video_id}. Last response: {json.dumps(last)}")


def cmd_video(args: argparse.Namespace) -> None:
    created = request_json("POST", "/v1/videos", video_payload(args))
    if not args.poll:
        task_id = created.get("id") or created.get("task_id")
        video_id = created.get("video_id")
        next_steps = []
        if task_id:
            next_steps.append(f"python scripts/agnes_api.py video-get {task_id}")
            next_steps.append(f"python scripts/agnes_api.py video-get {task_id}  # repeat until status is completed")
        if video_id:
            model_hint = f" --model-name {VIDEO_MODEL}"
            next_steps.append(f"python scripts/agnes_api.py video-get {task_id} --video-id {video_id}{model_hint}  # V2.0 recommended query")
            next_steps.append(f"curl -H 'Authorization: Bearer YOUR_KEY' 'https://apihub.agnes-ai.com/agnesapi?video_id={video_id}'  # V2.0 direct query")
        output_result(
            "video-task",
            created,
            prompt_used=getattr(args, "_prompt_used", None),
            translated_prompt=getattr(args, "_translated_prompt", None),
            status=str(created.get("status", "")) if created.get("status") is not None else None,
            next_steps=next_steps,
            raw_only=args.raw,
        )
        return

    # Polling phase — optionally wrap with live logging
    task_id = created.get("id") or created.get("task_id")
    video_id = created.get("video_id")
    if not task_id:
        raise SystemExit(f"Video create response did not include id: {json.dumps(created)}")

    def _poll_body():
        from agnes_logger import LiveLogger
        logger = LiveLogger("video-poll")
        logger.__enter__()
        try:
            data = poll_video(str(task_id), video_id, args.timeout, args.interval)
        finally:
            logger.__exit__(None, None, None)
        return data

    if args.live:
        data = _poll_body()
    else:
        data = poll_video(str(task_id), video_id, args.timeout, args.interval)

    urls = extract_video_urls(data)
    output_result(
        "video-result",
        data,
        prompt_used=getattr(args, "_prompt_used", None),
        translated_prompt=getattr(args, "_translated_prompt", None),
        urls=urls,
        status=str(data.get("status", "")) if data.get("status") is not None else None,
        raw_only=args.raw,
    )


def cmd_video_get(args: argparse.Namespace) -> None:
    from agnes_logger import LiveLogger

    if args.live:
        with LiveLogger("video-get") as log:
            _cmd_video_get_inner(args)
    else:
        _cmd_video_get_inner(args)


def _cmd_video_get_inner(args: argparse.Namespace) -> None:
    """Inner body for cmd_video_get (runs inside LiveLogger context when --live)."""
    if args.video_id:
        # V2.0 recommended: query by video_id via /agnesapi
        url = f"/agnesapi?video_id={args.video_id}"
        if args.model_name:
            url += f"&model_name={args.model_name}"
        data = request_json("GET", url)
    else:
        # Legacy: query by task_id via /v1/videos/{task_id}
        data = request_json("GET", f"/v1/videos/{args.task_id}")
    urls = extract_video_urls(data)
    next_steps_list = []
    if not urls and data.get("status") != "completed":
        if args.video_id:
            next_steps_list.append(f"python scripts/agnes_api.py video-get {args.task_id if args.task_id else '...'} --video-id {args.video_id}")
        else:
            next_steps_list.append(f"python scripts/agnes_api.py video-get {args.task_id}")
    output_result(
        "video-result",
        data,
        urls=urls,
        status=str(data.get("status", "")) if data.get("status") is not None else None,
        next_steps=next_steps_list if next_steps_list else None,
        raw_only=args.raw,
    )
    if data.get("error") and not urls:
        raise SystemExit(1)


def require_ok(name: str, data: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise SystemExit(f"{name} response missing {missing}: {json.dumps(data)}")
    print(f"{name}: ok")


def require_video_ok(name: str, data: dict[str, Any], completed: bool = False) -> None:
    require_ok(name, data, ("id", "status"))
    if data.get("error"):
        raise SystemExit(f"{name} returned error: {json.dumps(data, ensure_ascii=False)}")
    status = str(data.get("status", "")).lower()
    if status == "failed":
        raise SystemExit(f"{name} failed: {json.dumps(data, ensure_ascii=False)}")
    if completed and status != "completed":
        raise SystemExit(f"{name} did not complete: {json.dumps(data, ensure_ascii=False)}")
    if completed and not extract_video_urls(data):
        raise SystemExit(f"{name} completed without a video URL: {json.dumps(data, ensure_ascii=False)}")


def check_tool_call(name: str, data: dict[str, Any], strict: bool = False) -> None:
    try:
        tool_calls = data["choices"][0]["message"].get("tool_calls")
    except (KeyError, IndexError, TypeError, AttributeError):
        tool_calls = None
    if not tool_calls:
        message = f"{name}: request accepted, but response did not include tool_calls"
        if strict:
            raise SystemExit(f"{message}: {json.dumps(data, ensure_ascii=False)}")
        print(message, file=sys.stderr)
        return
    print(f"{name}: ok")


def extract_image_url(data: dict[str, Any]) -> str:
    candidates = extract_image_urls(data)
    if not candidates:
        raise SystemExit(f"Could not find image URL in response: {json.dumps(data, ensure_ascii=False)}")
    return candidates[0]


def create_video_case(name: str, payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    created = request_json("POST", "/v1/videos", payload)
    require_video_ok(f"{name}-create", created)
    task_id = str(created.get("id") or created.get("task_id", ""))
    video_id = created.get("video_id")
    retrieved = (
        poll_video(task_id, video_id, args.video_timeout, args.video_interval)
        if args.poll_video
        else request_json("GET", f"/v1/videos/{task_id}", timeout_val=120)
    )
    require_video_ok(f"{name}-get", retrieved, completed=args.poll_video)
    return {"create": created, "get": retrieved}


VIDEO_CASES = ("text-to-video", "image-to-video", "multi-image", "keyframes")


def cmd_smoke_test(args: argparse.Namespace) -> None:
    validate_size(args.image_size, "image-size")
    validate_video_args(
        argparse.Namespace(
            num_frames=args.video_num_frames,
            frame_rate=args.video_frame_rate,
            height=args.video_height,
            width=args.video_width,
        )
    )
    text = request_json(
        "POST",
        "/v1/chat/completions",
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: Agnes text ok"}],
            "max_tokens": 20,
            "temperature": 0,
        },
    )
    require_ok("text", text, ("choices",))

    text_stream = stream_summary(
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: Agnes stream ok"}],
            "max_tokens": 20,
            "temperature": 0,
            "stream": True,
        }
    )
    if text_stream["events"] < 1 and not text_stream["done"]:
        raise SystemExit(f"text-stream response did not look like SSE: {json.dumps(text_stream)}")
    print("text-stream: ok")

    text_tools = request_json(
        "POST",
        "/v1/chat/completions",
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Use the get_test_value tool."}],
            "max_tokens": 128,
            "temperature": 0,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_test_value",
                        "description": "Return a deterministic smoke test value.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "test label"}
                            },
                            "required": ["label"],
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "get_test_value"}},
        },
    )
    check_tool_call("text-tools", text_tools, strict=args.strict_tools)

    image_text = request_json(
        "POST",
        "/v1/images/generations",
        {
            "model": IMAGE_MODEL,
            "prompt": "A simple red square icon centered on a white background",
            "size": args.image_size,
            "extra_body": {"response_format": "url"},
        },
    )
    require_ok("image-text-to-image", image_text, ("data",))
    generated_image_url = extract_image_url(image_text)

    image_edit = None
    edited_image_url = None
    selected_cases = set(args.video_case or [])
    needs_second_image = bool(selected_cases.intersection({"multi-image", "keyframes"}))
    if args.include_image_edit or needs_second_image:
        image_edit = request_json(
            "POST",
            "/v1/images/generations",
            {
                "model": IMAGE_MODEL,
                "prompt": "Turn this into a clean blue square icon while preserving the centered composition",
                "size": args.image_size,
                "extra_body": {"image": [generated_image_url], "response_format": "url"},
            },
        )
        require_ok("image-to-image", image_edit, ("data",))
        edited_image_url = extract_image_url(image_edit)

    video_common = {
        "model": VIDEO_MODEL,
    }
    for key, value in (
        ("height", args.video_height),
        ("width", args.video_width),
        ("num_frames", args.video_num_frames),
        ("frame_rate", args.video_frame_rate),
    ):
        if value is not None:
            video_common[key] = value
    video_results = {}
    if "text-to-video" in selected_cases:
        video_results["text_to_video"] = create_video_case(
            "video-text-to-video",
            {
                **video_common,
                "prompt": "A simple cinematic shot of a red square gently moving on a white background",
            },
            args,
        )
    if "image-to-video" in selected_cases:
        video_results["image_to_video"] = create_video_case(
            "video-image-to-video",
            {
                **video_common,
                "prompt": "Animate the icon with subtle floating motion, stable centered composition",
                "image": generated_image_url,
            },
            args,
        )
    if "multi-image" in selected_cases:
        if not edited_image_url:
            raise SystemExit("multi-image test requires an edited image URL")
        video_results["multi_image"] = create_video_case(
            "video-multi-image",
            {
                **video_common,
                "prompt": "Create a smooth transformation from the first icon to the second icon, stable centered composition",
                "extra_body": {"image": [generated_image_url, edited_image_url]},
            },
            args,
        )
    if "keyframes" in selected_cases:
        if not edited_image_url:
            raise SystemExit("keyframes test requires an edited image URL")
        video_results["keyframes"] = create_video_case(
            "video-keyframes",
            {
                **video_common,
                "prompt": "Create a smooth keyframe transition between the two icons, stable centered composition",
                "extra_body": {"image": [generated_image_url, edited_image_url], "mode": "keyframes"},
            },
            args,
        )
    print_json(
        {
            "text": text,
            "text_stream": text_stream,
            "text_tools": text_tools,
            "image_text_to_image": image_text,
            "image_to_image": image_edit,
            "video": video_results,
        }
    )


def cmd_video_stitch(args: argparse.Namespace) -> None:
    """Stitch multiple videos together with seamless crossfade transitions using ffmpeg."""
    import subprocess
    import ssl
    import shutil

    videos = args.input_video
    if len(videos) < 2:
        raise SystemExit("--input-video requires at least 2 video URLs.")

    output = args.output or "stitched-video.mp4"
    fade_duration = args.fade_duration
    fade_duration_str = f"{fade_duration:.3f}s"

    # Download videos to temp directory
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="agnes-stitch-")
    try:
        downloaded = []
        for i, url in enumerate(videos):
            print(f"[{i+1}/{len(videos)}] Downloading {url}", file=sys.stderr)
            out_path = os.path.join(tmpdir, f"seg{i}.mp4")
            # Download with SSL bypass and retry on failure
            data = None
            for attempt in range(2):
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
                        data = resp.read()
                    break
                except Exception as exc:
                    if attempt == 0:
                        print(f"  SSL/network error, retrying... ({exc})", file=sys.stderr)
                        continue
                    raise SystemExit(f"Failed to download {url}: {exc}")
            if not data:
                raise SystemExit(f"Downloaded empty file for {url}")
            with open(out_path, "wb") as f:
                f.write(data)
            downloaded.append(out_path)

        # Check ffmpeg is available
        if not shutil.which("ffmpeg"):
            raise SystemExit(
                "ffmpeg is required for video stitching. Install it with: brew install ffmpeg"
            )

        # Build concat list
        concat_file = os.path.join(tmpdir, "concat-list.txt")
        with open(concat_file, "w") as f:
            for p in downloaded:
                f.write(f"file '{os.path.basename(p)}'\n")

        # First pass: concat without filters to get total duration and ensure compatibility
        concat_out = os.path.join(tmpdir, "concatenated.mp4")
        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            concat_out,
        ]
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"Concat failed: {result.stderr}")

        # Get durations of each segment for precise xfade placement
        durations = []
        for p in downloaded:
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", p],
                    capture_output=True, text=True,
                )
                dur = float(probe.stdout.strip())
                durations.append(dur)
            except Exception:
                # Default to 5s if probe fails
                durations.append(5.0)

        total_duration = sum(durations)
        num_transitions = len(downloaded) - 1
        xfade_duration = min(fade_duration, total_duration / (num_transitions * 2))

        # Build xfade filtergraph
        # First xfade: seg[0:v] and seg[1:v] -> xfade0
        # Then: xfade0 and seg[2:v] -> xfade1, etc.
        # For n inputs: need n-1 xfade operations
        input_args: list[str] = []
        for p in downloaded:
            input_args.extend(["-i", p])

        n = len(downloaded)
        # Build video xfade chain
        video_filter = ""
        if n == 2:
            t = durations[0] - xfade_duration
            video_filter = f"[0:v][1:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={t:.3f}[vout]"
        else:
            video_filter = f"[0:v][1:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={durations[0] - xfade_duration:.3f}[xf0]"
            offset_v = durations[0] + durations[1] - 2 * xfade_duration
            for i in range(2, n):
                prev = "[xf0]" if i == 2 else f"[xf{i-2}]"
                label = f"[xf{i-1}]" if i < n - 1 else "[vout]"
                video_filter += f";{prev}[{i}:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={offset_v:.3f}{label}"
                offset_v += durations[i] - xfade_duration

        # Build audio acrossfade chain (using duration only, no c1/c2 mode)
        audio_filter = ""
        if n == 2:
            audio_filter = f"[0:a][1:a]acrossfade=duration={xfade_duration:.3f}[aout]"
        else:
            audio_filter = f"[0:a][1:a]acrossfade=duration={xfade_duration:.3f}[a0]"
            offset_a = durations[0] - xfade_duration
            for i in range(2, n):
                prev = "[a0]" if i == 2 else f"[a{i-2}]"
                label = f"[a{i-1}]" if i < n - 1 else "[aout]"
                audio_filter += f";{prev}[{i}:a]acrossfade=duration={xfade_duration:.3f}{label}"
                offset_a += durations[i] - xfade_duration

        filter_complex = video_filter + ";" + audio_filter

        cmd = ["ffmpeg", "-y"] + input_args
        cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        cmd.append(output)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Stitch with crossfade failed: {result.stderr}", file=sys.stderr)
            print("Falling back to simple concat (no crossfade)...", file=sys.stderr)
            concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                          "-i", concat_file, "-c", "copy", output]
            result2 = subprocess.run(concat_cmd, capture_output=True, text=True)
            if result2.returncode != 0:
                raise SystemExit(f"Stitching failed: {result2.stderr}")

        # Get final duration
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", output],
                capture_output=True, text=True,
            )
            final_dur = float(probe.stdout.strip())
        except Exception:
            final_dur = total_duration

        print_json({
            "type": "video-stitch",
            "status": "completed",
            "output": output,
            "urls": [output],
            "input_count": len(downloaded),
            "duration_seconds": round(final_dur, 2),
            "transition": "fade",
            "fade_duration": round(fade_duration, 2),
            "segments": [
                {"url": url, "path": downloaded[i]} for i, url in enumerate(videos)
            ],
        })

    finally:
        # Cleanup temp dir
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)


def cmd_video_storyboard(args: argparse.Namespace) -> None:
    """Generate a professional storyboard from a story prompt using the text API."""
    payload: dict[str, Any] = {
        "model": TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional storyboard artist and cinematic director. "
                    "Given a story description, create a detailed video storyboard. "
                    "Return ONLY a valid JSON array. No markdown, no explanation.\n\n"
                    "Each segment must have:\n"
                    "- shot: English description of what the viewer sees (unique per segment)\n"
                    "- action: what characters are doing in this shot\n"
                    "- camera: camera movement (wide shot, close-up, tracking, pan, tilt, dolly, etc.)\n"
                    "- mood: emotional tone (tense, peaceful, dramatic, etc.)\n"
                    "- lighting: lighting description\n"
                    "- duration: target segment duration (default 10)\n"
                    "- characters: list of character names appearing in this shot\n\n"
                    "CRITICAL RULES:\n"
                    "1. Each segment must be VISUALLY DISTINCT — no repeating shots\n"
                    "2. Track character states across segments (e.g., snake frozen → snake revived → snake attacks)\n"
                    "3. Include camera variation (wide, close-up, tracking, overhead, etc.)\n"
                    "4. Build tension/flow: beginning → rising action → climax → resolution\n"
                    "5. Include transitions between scenes\n"
                    "6. Total duration should be approximately num_segments * duration seconds\n"
                    "7. Use English for all descriptions\n"
                    "8. Keep prompts under 200 words each (for video API prompt limits)\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create a video storyboard for: {args.story}\n\n"
                    f"Requirements:\n"
                    f"- {args.num_segments} segments\n"
                    f"- Each segment ~{args.duration} seconds\n"
                    f"- Output format: JSON array of segment objects\n"
                    f"- Include character tracking across segments\n"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 4096,
    }
    data = request_json("POST", "/v1/chat/completions", payload)
    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Storyboard generation failed: {json.dumps(data, ensure_ascii=False)}") from exc

    # Parse JSON from response (may be wrapped in markdown code blocks)
    import re as _re
    json_str = content
    if "```json" in content:
        json_str = _re.search(r"```json\s*\n(.*?)```", content, _re.DOTALL).group(1)
    elif "```" in content:
        json_str = _re.search(r"```\s*\n(.*?)```", content, _re.DOTALL).group(1)

    try:
        storyboard = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Storyboard JSON parse error: {exc.msg}\nRaw response: {content[:500]}") from exc

    # Validate and normalize segments
    normalized = []
    for i, seg in enumerate(storyboard):
        normalized.append({
            "segment": i + 1,
            "shot": seg.get("shot", f"Segment {i+1}"),
            "action": seg.get("action", ""),
            "camera": seg.get("camera", "static shot"),
            "mood": seg.get("mood", "neutral"),
            "lighting": seg.get("lighting", "natural light"),
            "duration": seg.get("duration", args.duration),
            "characters": seg.get("characters", []),
        })

    result = {
        "type": "video-storyboard",
        "story": args.story,
        "num_segments": len(normalized),
        "segments": normalized,
    }
    print_json(result)


def cmd_video_download(args: argparse.Namespace) -> None:
    """Download videos from URLs to local files."""
    from agnes_logger import LiveLogger

    if args.live:
        with LiveLogger("video-download") as log:
            _cmd_video_download_inner(args)
    else:
        _cmd_video_download_inner(args)


def _cmd_video_download_inner(args: argparse.Namespace) -> None:
    """Inner body for cmd_video_download (runs inside LiveLogger context)."""
    import ssl
    import shutil

    urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    if not urls:
        raise SystemExit("No URLs provided.")

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    downloaded = []
    for i, url in enumerate(urls):
        out_path = os.path.join(output_dir, f"video_{i:03d}.mp4")
        print(f"[{i+1}/{len(urls)}] Downloading {url}", file=sys.stderr)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
                data = resp.read()
        except Exception as exc:
            print(f"  Failed: {exc}", file=sys.stderr)
            continue
        with open(out_path, "wb") as f:
            f.write(data)
        downloaded.append({"url": url, "path": out_path})
        print(f"  Saved: {out_path}", file=sys.stderr)

    print_json({
        "type": "video-download",
        "status": "completed",
        "output_dir": output_dir,
        "downloaded_count": len(downloaded),
        "files": downloaded,
    })


def cmd_video_batch(args: argparse.Namespace) -> None:
    """Full pipeline: generate storyboard (optional) → character refs → parallel video generation → download → stitch."""
    import ssl
    import tempfile
    import shutil
    import concurrent.futures

    from agnes_logger import LiveLogger

    def _print_cleanup(log_path, tail_pid):
        print(f"[Pipeline done, log file: {log_path}]", file=sys.stderr, flush=True)

    with LiveLogger("video-batch", print_cleanup=_print_cleanup) as log:
        # Step 1: Generate or load storyboard
        storyboard = None
        if args.storyboard:
            with open(args.storyboard, "r") as f:
                sb_data = json.load(f)
            storyboard = sb_data.get("segments") if isinstance(sb_data, dict) else sb_data
            if not storyboard:
                raise SystemExit(f"Storyboard file has no 'segments' key: {json.dumps(sb_data, ensure_ascii=False)[:200]}")
            print(f"Loaded storyboard: {len(storyboard)} segments", file=sys.stderr)
        elif args.story:
            print("Generating storyboard from story...", file=sys.stderr)
            sb_payload: dict[str, Any] = {
                "model": TEXT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a professional storyboard artist. Return ONLY valid JSON array. "
                            "Each segment: {shot, action, camera, mood, lighting, duration, characters}. "
                            "CRITICAL: Each segment must be VISUALLY DISTINCT. Track character states."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Create a video storyboard for: {args.story}\n\n"
                            f"- {args.num_segments} segments, each ~{args.duration}s\n"
                            f"- Output format: JSON array"
                        ),
                    },
                ],
                "temperature": 0,
                "max_tokens": 4096,
            }
            sb_data = request_json("POST", "/v1/chat/completions", sb_payload)
            content = sb_data["choices"][0]["message"]["content"].strip()
            import re as _re
            json_str = content
            if "```json" in content:
                json_str = _re.search(r"```json\s*\n(.*?)```", content, _re.DOTALL).group(1)
            elif "```" in content:
                json_str = _re.search(r"```\s*\n(.*?)```", content, _re.DOTALL).group(1)
            try:
                raw_storyboard = json.loads(json_str)
                storyboard = raw_storyboard if isinstance(raw_storyboard, list) else raw_storyboard.get("segments", raw_storyboard)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Storyboard parse error: {exc}\nResponse: {content[:500]}") from exc
        else:
            raise SystemExit("Provide --story or --storyboard to generate videos.")

        storyboard = [
            {
                "segment": i + 1,
                "shot": s.get("shot", ""),
                "action": s.get("action", ""),
                "camera": s.get("camera", "static shot"),
                "mood": s.get("mood", "neutral"),
                "lighting": s.get("lighting", "natural light"),
                "duration": s.get("duration", args.duration),
                "characters": s.get("characters", []),
            }
            for i, s in enumerate(storyboard)
        ]

        print(f"Storyboard: {len(storyboard)} segments", file=sys.stderr)

        # Step 2: Collect unique character names and generate ref images
        all_characters = set()
        for seg in storyboard:
            for c in seg.get("characters", []):
                if isinstance(c, dict):
                    all_characters.add(c.get("name", str(c)))
                else:
                    all_characters.add(str(c))
        all_characters = list(all_characters)

        character_images = {}  # character_name -> URL
        if all_characters:
            print(f"Generating {len(all_characters)} character reference images...", file=sys.stderr)
            for char_name in all_characters:
                seed = hash(char_name) % 100000
                print(f"  Generating character ref: {char_name} (seed={seed})", file=sys.stderr)
                char_payload: dict[str, Any] = {
                    "model": IMAGE_MODEL,
                    "prompt": (
                        f"Professional character design sheet of {char_name}. "
                        f"Full body, front view, clear details of clothing, hair, and accessories. "
                        f"Cinematic, detailed, consistent character identity."
                    ),
                    "size": "1280x768",
                    "seed": seed,
                }
                extra = {"response_format": "url"}
                char_payload["extra_body"] = extra
                char_data = request_json("POST", "/v1/images/generations", char_payload)
                urls = extract_image_urls(char_data)
                if urls:
                    character_images[char_name] = urls[0]
                    print(f"  Character ref ready: {char_name} -> {urls[0]}", file=sys.stderr)
                else:
                    print(f"  WARNING: Failed to generate character ref for {char_name}", file=sys.stderr)

        # Step 3: Prepare video payloads for all segments
        video_payloads = []
        for seg in storyboard:
            prompt_parts = []
            for key in ("shot", "action"):
                if seg.get(key):
                    prompt_parts.append(str(seg[key]))
            if seg.get("camera"):
                prompt_parts.append(f"Camera: {seg['camera']}.")
            if seg.get("mood"):
                prompt_parts.append(f"Mood: {seg['mood']}.")
            if seg.get("lighting"):
                prompt_parts.append(f"Lighting: {seg['lighting']}.")
            prompt = " ".join(prompt_parts) if prompt_parts else str(seg.get("shot", ""))

            vp: dict[str, Any] = {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "width": 1280,
                "height": 768,
                "num_frames": 241,
                "frame_rate": 24,
            }
            # Collect character ref URLs for this segment
            seg_chars = seg.get("characters", [])
            if seg_chars:
                seg_refs = []
                for c in seg_chars:
                    char_name = c.get("name") if isinstance(c, dict) else c
                    if char_name in character_images:
                        seg_refs.append(character_images[char_name])
                if seg_refs:
                    if len(seg_refs) == 1:
                        vp["image"] = seg_refs[0]
                        vp["mode"] = "ti2vid"
                    else:
                        vp["extra_body"] = {"image": seg_refs, "mode": "keyframes"}
                        vp["mode"] = "keyframes"

            video_payloads.append({
                "payload": vp,
                "segment": seg,
                "prompt_used": prompt,
            })

        # Step 4: Submit all video tasks with progress reporting
        total_segments = len(video_payloads)
        print(f"Submitting {total_segments} video tasks...", file=sys.stderr)

        def format_eta(elapsed, progress):
            if progress and progress > 0 and progress < 100:
                estimated_total = elapsed / (progress / 100.0)
                remaining = elapsed - elapsed
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                return f"ETA {mins}m{secs}s"
            return ""

        task_results = {}  # seg_num -> task info
        completed_count = 0

        for vp in video_payloads:
            seg = vp["segment"]
            seg_num = seg["segment"]
            # Stagger submissions to avoid connection drops
            if seg_num > 1:
                time.sleep(2)
            try:
                print(f"  Submitting segment {seg_num}/{total_segments}: {seg.get('action', '')[:60]}...", file=sys.stderr)
                created = request_json("POST", "/v1/videos", vp["payload"])
                task_id = str(created.get("id") or created.get("task_id", ""))
                video_id = created.get("video_id")
                status = str(created.get("status", ""))
                print(f"  ✓ Segment {seg_num} submitted: task={task_id}, status={status}", file=sys.stderr)
                task_results[seg_num] = {
                    "task_id": task_id,
                    "video_id": video_id,
                    "status": status,
                }
            except Exception as exc:
                print(f"  ✗ Segment {seg_num} FAILED: {exc}", file=sys.stderr)
                task_results[seg_num] = {"error": str(exc)}

        # Summary after submission
        submitted = sum(1 for r in task_results.values() if "error" not in r)
        failed = sum(1 for r in task_results.values() if "error" in r)
        print(f"\nSubmission summary: {submitted}/{total_segments} succeeded, {failed} failed\n", file=sys.stderr)

        # Collect all task IDs for polling
        pending = {}
        for seg_num, task_result in task_results.items():
            if "error" not in task_result:
                pending[seg_num] = task_result

        # Poll all tasks with real-time progress
        if pending:
            print("=" * 60, file=sys.stderr)
            print("Polling video tasks for completion...", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            poll_start = time.time()

            max_poll_rounds = 600  # ~1 hour max
            round_num = 0
            still_pending = set(pending.keys())

            while still_pending and round_num < max_poll_rounds:
                round_num += 1
                elapsed = time.time() - poll_start

                # Print progress header every 3 rounds
                if round_num % 3 == 1 or round_num <= 2:
                    bar_width = 30
                    done_count = total_segments - len(still_pending)
                    overall_progress = (done_count / total_segments) * 100
                    bar_done = int(bar_width * done_count / total_segments)
                    bar = "█" * bar_done + "░" * (bar_width - bar_done)
                    eta_str = ""
                    for seg_num in still_pending:
                        info = pending[seg_num]
                        if "progress" in info and info["progress"] and 0 < info["progress"] < 100:
                            eta_str = format_eta(elapsed, info["progress"])
                            break
                    print(f"\r[{bar}] {overall_progress:.0f}% — {done_count}/{total_segments} done  {eta_str}", end="", file=sys.stderr, flush=True)

                for seg_num in list(still_pending):
                    info = pending[seg_num]
                    try:
                        if info.get("video_id"):
                            data = request_json("GET", f"/agnesapi?video_id={info['video_id']}")
                        else:
                            data = request_json("GET", f"/v1/videos/{info['task_id']}")
                        status = str(data.get("status", "")).lower()
                        progress = data.get("progress")  # int or None

                        pending[seg_num] = {**info, **data}

                        if status == "completed":
                            still_pending.discard(seg_num)
                            completed_count += 1
                            # Print completion immediately
                            bar_width = 30
                            done_count = total_segments - len(still_pending)
                            overall_progress = (done_count / total_segments) * 100
                            bar_done = int(bar_width * done_count / total_segments)
                            bar = "█" * bar_done + "░" * (bar_width - bar_done)
                            print(f"\r[{bar}] {overall_progress:.0f}% — Segment {seg_num} COMPLETED ✓", end="", file=sys.stderr, flush=True)
                        elif status == "failed":
                            still_pending.discard(seg_num)
                            print(f"\n  ✗ Segment {seg_num} FAILED: {json.dumps(data, ensure_ascii=False)[:200]}", file=sys.stderr)
                        else:
                            # Update progress display
                            if progress and progress > 0 and progress < 100:
                                seg_progress = f"seg{seg_num}_p{progress}"
                    except Exception as exc:
                        print(f"\n  Poll error segment {seg_num}: {exc}", file=sys.stderr)

                # Print intermediate status
                if still_pending:
                    if round_num % 3 == 0:
                        # Print current status of pending segments
                        pending_info = []
                        for sn in still_pending:
                            p = pending[sn].get("progress")
                            if p and 0 < p < 100:
                                pending_info.append(f"{sn}({p}%)")
                            else:
                                pending_info.append(f"{sn}(?)")
                        print(f"\r[{round_num}] Pending: {', '.join(pending_info)}", end="", file=sys.stderr, flush=True)

                # Sleep with decreasing interval as we get closer
                sleep_time = min(10, max(2, 30 - round_num))
                if still_pending:
                    time.sleep(sleep_time)

            # Clear the progress line
            print(file=sys.stderr, flush=True)

        # Final summary
        print(f"\nPolling complete: {total_segments - len(still_pending)}/{total_segments} videos processed", file=sys.stderr)

        # Step 4.5: Retry failed segments before stitching
        failed_seg_nums = [s for s in task_results if "error" in task_results[s]]
        if failed_seg_nums:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print(f"Retrying {len(failed_seg_nums)} failed segment(s) before stitching...", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            successful_retries = []
            for seg_num in failed_seg_nums:
                # Find the original vp entry for this segment
                vp_entry = None
                for vp in video_payloads:
                    if vp["segment"]["segment"] == seg_num:
                        vp_entry = vp
                        break
                if not vp_entry:
                    print(f"  ✗ Segment {seg_num}: no payload found for retry", file=sys.stderr)
                    continue
                try:
                    print(f"  Retrying segment {seg_num}...", file=sys.stderr)
                    time.sleep(3)
                    created = request_json("POST", "/v1/videos", vp_entry["payload"])
                    task_id = str(created.get("id") or created.get("task_id", ""))
                    video_id = created.get("video_id")
                    print(f"  ✓ Segment {seg_num} resubmitted: task={task_id}", file=sys.stderr)
                    successful_retries.append((seg_num, video_id, task_id))
                except Exception as exc:
                    print(f"  ✗ Segment {seg_num} retry FAILED: {exc}", file=sys.stderr)
                    task_results[seg_num]["error"] = f"retry: {exc}"

            # Poll retry tasks
            if successful_retries:
                retry_info = {sn: {"video_id": vid, "task_id": tid} for sn, vid, tid in successful_retries}
                retry_pending = set(sn for sn, _, _ in successful_retries)
                max_retry_rounds = 600
                rr = 0
                while retry_pending and rr < max_retry_rounds:
                    rr += 1
                    for seg_num in list(retry_pending):
                        info = retry_info[seg_num]
                        try:
                            if info.get("video_id"):
                                data = request_json("GET", f"/agnesapi?video_id={info['video_id']}")
                            else:
                                data = request_json("GET", f"/v1/videos/{info['task_id']}")
                            status = str(data.get("status", "")).lower()
                            retry_info[seg_num] = {**info, **data}
                            if status in ("completed", "failed"):
                                retry_pending.discard(seg_num)
                                if status == "completed":
                                    completed_count += 1
                                    print(f"  ✓ Segment {seg_num} retry COMPLETED", file=sys.stderr)
                                else:
                                    print(f"  ✗ Segment {seg_num} retry FAILED", file=sys.stderr)
                        except Exception as exc:
                            print(f"  Retry poll error segment {seg_num}: {exc}", file=sys.stderr)
                    if retry_pending:
                        time.sleep(min(10, max(2, 20 - rr)))
                print(f"  Retry complete: {len(successful_retries) - len(retry_pending)}/{len(successful_retries)} segments succeeded", file=sys.stderr)

                # Merge retry results into pending dict
                for seg_num, data in retry_info.items():
                    if "error" not in pending.get(seg_num, {}):
                        pending[seg_num] = data

        # Step 5: Download all completed videos
        print("Downloading videos...", file=sys.stderr)
        tmpdir = tempfile.mkdtemp(prefix="agnes-batch-")
        try:
            segment_videos = []  # list of (seg_num, url, local_path)
            for seg_num in sorted(pending.keys()):
                info = pending[seg_num]
                if info.get("error"):
                    print(f"  Segment {seg_num}: still has error, skipping", file=sys.stderr)
                    continue
                video_url = extract_video_urls(info)
                if not video_url:
                    print(f"  Segment {seg_num}: no video URL found", file=sys.stderr)
                    continue
                video_url = video_url[0]
                local_path = os.path.join(tmpdir, f"seg{seg_num:03d}.mp4")
                print(f"  Downloading segment {seg_num}: {video_url}", file=sys.stderr)
                try:
                    for dl_attempt in range(1, 4):
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        req = urllib.request.Request(video_url, method="GET")
                        with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
                            data = resp.read()
                        with open(local_path, "wb") as f:
                            f.write(data)
                        segment_videos.append((seg_num, video_url, local_path))
                        break
                    else:
                        print(f"  ✗ Download failed segment {seg_num}: max retries exceeded", file=sys.stderr)
                except Exception as exc:
                    if dl_attempt < 3:
                        print(f"  Download retry segment {seg_num} ({dl_attempt}/3): {exc}", file=sys.stderr)
                        time.sleep(2)
                    else:
                        print(f"  ✗ Download failed segment {seg_num}: {exc}", file=sys.stderr)

            # Sort by segment number
            segment_videos.sort(key=lambda x: x[0])

            # Step 6: Stitch all videos
            print("Stitching videos...", file=sys.stderr)
            if not segment_videos:
                raise SystemExit("No videos were successfully generated or downloaded.")

            concat_file = os.path.join(tmpdir, "concat-list.txt")
            with open(concat_file, "w") as f:
                for _, _, local_path in segment_videos:
                    f.write(f"file '{os.path.basename(local_path)}'\n")

            output = args.output or "output-video.mp4"

            # Try xfade first
            durations = []
            for _, _, local_path in segment_videos:
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", local_path],
                        capture_output=True, text=True,
                    )
                    durations.append(float(probe.stdout.strip()))
                except Exception:
                    durations.append(10.0)

            n = len(segment_videos)
            xfade_duration = min(0.8, sum(durations) / (n * 2))

            input_args = []
            for _, _, local_path in segment_videos:
                input_args.extend(["-i", local_path])

            video_filter = ""
            if n == 2:
                video_filter = f"[0:v][1:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={durations[0] - xfade_duration:.3f}[vout]"
            else:
                video_filter = f"[0:v][1:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={durations[0] - xfade_duration:.3f}[xf0]"
                offset_v = durations[0] + durations[1] - 2 * xfade_duration
                for i in range(2, n):
                    prev = "[xf0]" if i == 2 else f"[xf{i-2}]"
                    label = f"[xf{i-1}]" if i < n - 1 else "[vout]"
                    video_filter += f";{prev}[{i}:v]xfade=transition=fade:duration={xfade_duration:.3f}:offset={offset_v:.3f}{label}"
                    offset_v += durations[i] - xfade_duration

            audio_filter = ""
            if n == 2:
                audio_filter = f"[0:a][1:a]acrossfade=duration={xfade_duration:.3f}[aout]"
            else:
                audio_filter = f"[0:a][1:a]acrossfade=duration={xfade_duration:.3f}[a0]"
                offset_a = durations[0] - xfade_duration
                for i in range(2, n):
                    prev = "[a0]" if i == 2 else f"[a{i-2}]"
                    label = f"[a{i-1}]" if i < n - 1 else "[aout]"
                    audio_filter += f";{prev}[{i}:a]acrossfade=duration={xfade_duration:.3f}{label}"
                    offset_a += durations[i] - xfade_duration

            filter_complex = video_filter + ";" + audio_filter

            cmd = ["ffmpeg", "-y"] + input_args
            cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
            cmd.append(output)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Stitch with crossfade failed, falling back to simple concat...", file=sys.stderr)
                concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                              "-i", concat_file, "-c", "copy", output]
                subprocess.run(concat_cmd, capture_output=True, text=True)

            # Get final duration
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", output],
                    capture_output=True, text=True,
                )
                final_dur = float(probe.stdout.strip())
            except Exception:
                final_dur = sum(durations)

            print_json({
                "type": "video-batch",
                "status": "completed",
                "output": output,
                "urls": [output],
                "num_segments": len(segment_videos),
                "duration_seconds": round(final_dur, 2),
                "character_refs": character_images,
                "segments": [
                    {
                        "segment": seg_num,
                        "shot": seg["shot"],
                        "action": seg["action"],
                        "url": url,
                        "path": local_path,
                    }
                    for seg_num, url, local_path, seg in zip(
                        [sv[0] for sv in segment_videos],
                        [sv[1] for sv in segment_videos],
                        [sv[2] for sv in segment_videos],
                        [sv["segment"] for sv in video_payloads]
                    )
                ],
            })
        finally:
            # Cleanup temp dir (inside LiveLogger so stderr is restored)
            shutil.rmtree(tmpdir, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call Agnes AI generation APIs.")
    sub = parser.add_subparsers(dest="command", required=True)

    text = sub.add_parser("text", help="Create a chat completion.")
    text.add_argument("--prompt", required=True)
    text.add_argument("--system")
    text.add_argument("--temperature", type=float, default=0.7)
    text.add_argument("--top-p", type=float)
    text.add_argument("--max-tokens", type=int, default=1024)
    text.add_argument("--stream", action="store_true")
    text.add_argument("--tools-json", help="JSON array for OpenAI-compatible tool definitions.")
    text.add_argument("--tool-choice-json", help="JSON object/string for OpenAI-compatible tool_choice.")
    text.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    text.set_defaults(func=cmd_text)

    image = sub.add_parser("image", help="Generate or edit an image.")
    image.add_argument("--prompt", required=True)
    image.add_argument("--size", default="1024x768")
    image.add_argument("--seed", type=int)
    image.add_argument("--image", action="append", help="Input image URL. Repeat for multiple images.")
    image.add_argument(
        "--no-translate-prompt",
        action="store_true",
        help="Do not translate non-English prompts before sending to the image API.",
    )
    image.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    image.set_defaults(func=cmd_image)

    video = sub.add_parser("video", help="Create a video task.")
    video.add_argument("--prompt", required=True)
    video.add_argument("--image", action="append", help="Input image URL. Repeat for multi-image or keyframes.")
    video.add_argument(
        "--character-ref",
        action="append",
        help="Character reference image URL for consistent character appearance. Same refs across segments keep characters consistent. Can be used with --image for multi-image/keyframes.",
    )
    video.add_argument("--mode", choices=("ti2vid", "keyframes"))
    video.add_argument("--height", type=int)
    video.add_argument("--width", type=int)
    video.add_argument("--num-frames", type=int, default=121)
    video.add_argument("--frame-rate", type=float, default=24)
    video.add_argument("--num-inference-steps", type=int)
    video.add_argument("--seed", type=int)
    video.add_argument("--negative-prompt")
    video.add_argument("--duration", type=float,
        help="Target duration in seconds. Auto-sets num_frames and frame_rate. "
             "Supported values: 3 (~81/24), 5 (~121/24), 10 (~241/24), 18 (~441/24). "
             "Default: 5."),
    video.add_argument(
        "--no-translate-prompt",
        action="store_true",
        help="Do not translate non-English prompts before sending to the video API.",
    )
    video.add_argument("--poll", action="store_true")
    video.add_argument("--timeout", type=int, default=900)
    video.add_argument("--interval", type=int, default=10)
    video.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    video.add_argument("--live", action="store_true", help="Show real-time progress via tail -f.")
    video.set_defaults(func=cmd_video)

    video_get = sub.add_parser("video-get", help="Retrieve a video task.")
    video_get.add_argument("task_id", nargs="?", help="Legacy task_id (for /v1/videos/{task_id} endpoint)")
    video_get.add_argument("--video-id", dest="video_id", help="V2.0 video_id (for /agnesapi endpoint, recommended)")
    video_get.add_argument("--model-name", dest="model_name", help="Explicitly specify model name for query (V2.0)")
    video_get.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    video_get.add_argument("--live", action="store_true", help="Show real-time progress via tail -f.")
    video_get.set_defaults(func=cmd_video_get)

    video_stitch = sub.add_parser("video-stitch", help="Stitch multiple videos into one with seamless transitions.")
    video_stitch.add_argument(
        "--input-video", "-i",
        action="append",
        required=True,
        dest="input_video",
        help="Input video URL to stitch. Repeat for multiple videos.",
    )
    video_stitch.add_argument(
        "--output", "-o",
        default="stitched-video.mp4",
        help="Output file path (default: stitched-video.mp4).",
    )
    video_stitch.add_argument(
        "--fade-duration",
        type=float,
        default=0.8,
        help="Crossfade duration in seconds at each transition (default: 0.8).",
    )
    video_stitch.add_argument(
        "--with-audio",
        action="store_true",
        default=True,
        help="Include audio crossfading (default: True).",
    )
    video_stitch.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    video_stitch.set_defaults(func=cmd_video_stitch)

    smoke = sub.add_parser("smoke-test", help="Run live text, image, and video API tests.")
    smoke.add_argument("--image-size", default="1024x768")
    smoke.add_argument("--video-height", type=int)
    smoke.add_argument("--video-width", type=int)
    smoke.add_argument("--video-num-frames", type=int, default=81)
    smoke.add_argument("--video-frame-rate", type=float, default=24)
    smoke.add_argument("--include-image-edit", action="store_true", help="Also test image-to-image editing.")
    smoke.add_argument("--strict-tools", action="store_true", help="Fail if the tool-calling response has no tool_calls.")
    smoke.add_argument("--poll-video", action="store_true")
    smoke.add_argument("--video-timeout", type=int, default=900)
    smoke.add_argument("--video-interval", type=int, default=10)
    smoke.add_argument(
        "--video-case",
        action="append",
        choices=VIDEO_CASES,
        help="Video case to test. Repeat to test multiple cases. Omit to skip video creation.",
    )
    smoke.set_defaults(func=cmd_smoke_test)

    # video-storyboard: auto-generate storyboard from story
    sb = sub.add_parser("video-storyboard", help="Generate a professional video storyboard from a story.")
    sb.add_argument("--story", required=True, help="Story description or theme.")
    sb.add_argument("--num-segments", type=int, default=6, help="Number of segments (default: 6).")
    sb.add_argument("--duration", type=float, default=10.0, help="Duration per segment in seconds (default: 10).")
    sb.set_defaults(func=cmd_video_storyboard)

    # video-download: download videos from URLs
    vd = sub.add_parser("video-download", help="Download videos from URLs to local files.")
    vd.add_argument("--urls", required=True, help="Comma-separated video URLs to download.")
    vd.add_argument("--output-dir", default="./downloads", help="Output directory (default: ./downloads).")
    vd.add_argument("--live", action="store_true", help="Show real-time progress via tail -f.")
    vd.set_defaults(func=cmd_video_download)

    # video-batch: full pipeline (storyboard → images → videos → download → stitch)
    vb = sub.add_parser("video-batch", help="Full video pipeline: generate storyboard, character refs, videos, download, and stitch.")
    vb.add_argument("--story", help="Story description (used with --num-segments to auto-generate storyboard).")
    vb.add_argument("--storyboard", help="Path to pre-generated storyboard JSON file (overrides --story).")
    vb.add_argument("--num-segments", type=int, default=6, help="Number of segments (default: 6).")
    vb.add_argument("--duration", type=float, default=10.0, help="Duration per segment in seconds (default: 10).")
    vb.add_argument("--output", default="output-video.mp4", help="Output file path (default: output-video.mp4).")
    vb.set_defaults(func=cmd_video_batch)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
