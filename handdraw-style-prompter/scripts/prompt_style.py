#!/usr/bin/env python3
"""Create a deterministic bilingual prompt draft from a validated style number."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_reference import resolve

GRAPHIC_TEXT_SUFFIX = "【如果主题直白包含画面元素那就按主题出图，文案由你来升华，但是不要直接描述画面。 如果主题比较概念化，那么文案和主题尽量保持一致，如果文案较长由你提炼，由你先设计画面隐喻（人类和非人类都行）再出图   。    文字参与构图，图文一体】"

PURE_IMAGE_NOTE = "当前处于纯图模式，可切换为图文模式。"

REFERENCE_ISOLATION_ZH = "所附图片仅用于参考画风。只提取参考图的风格特征，例如线条、笔触、媒介、材质、色彩倾向和整体视觉语言；不要使用、复制或延续参考图中的任何主体、人物、动物、服装、道具、动作、姿态、场景、背景、构图、布局、文字或故事。最终画面内容完全以用户提供的主题为准。"
REFERENCE_ISOLATION_EN = "Use the attached image only as a style reference. Extract only its stylistic qualities, such as linework, brushwork, medium, material texture, color tendencies, and overall visual language. Do not use, copy, or carry over any subject, person, animal, clothing, prop, action, pose, setting, background, composition, layout, text, or story from the reference image. The user's written theme is the sole source for the image content."
REFERENCE_UPLOAD_ZH = "参考图：请上传本地参考图"
REFERENCE_UPLOAD_EN = "Reference image: upload local reference image"

# Concrete reference model used by the CLI convenience check; the conversational
# agent resolves the actual model against model_capabilities.json instead.
DEFAULT_MODEL = "gpt-image-2"


def positive_traits(traits: str) -> str:
    if not traits:
        return ""
    parts = [part.strip() for part in traits.replace("。", "；").split("；")]
    return "；".join(
        part for part in parts
        if part and not any(word in part for word in ("避免", "不要", "不准", "禁止"))
    )


def build_body(number: str, gen: str, reference: str, theme: str,
               traits: str, use_ref: bool, reference_path: str | None,
               extra_zh: str, extra_en: str, mode: str) -> tuple[str, str, str | None]:
    zh = f"风格名称：#{number} · {gen}。主题：{theme}。参考作者/风格名称：{reference}。"
    en = f"Style name: #{number} · {gen}. Theme: {theme}. Reference author/style name: {reference}."
    if traits:
        zh += f"核心风格特征：{traits}。"
        en += f" Core style traits: {traits}."
    if extra_zh:
        zh += f"；{extra_zh}"
        en += f" {extra_en}."

    shown_reference: str | None = None
    if mode == "graphic-text":
        # Theme is preserved verbatim; the fixed suffix is appended once per language.
        # A required reference image is shown outside the copyable prompts only.
        zh += "\n" + GRAPHIC_TEXT_SUFFIX
        en += "\n" + GRAPHIC_TEXT_SUFFIX
        if use_ref and reference_path:
            shown_reference = reference_path
    else:
        if use_ref and reference_path:
            zh += f"\n{REFERENCE_UPLOAD_ZH}：{reference_path}\n{REFERENCE_ISOLATION_ZH}"
            en += f"\n{REFERENCE_UPLOAD_EN}: {reference_path}\n{REFERENCE_ISOLATION_EN}"
        zh += f"\n\n{PURE_IMAGE_NOTE}"
        en += f"\n\n{PURE_IMAGE_NOTE}"
    return zh, en, shown_reference


def main() -> None:
    styles = json.loads((SKILL / "references" / "styles.json").read_text(encoding="utf-8"))
    max_num = len(styles)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", required=True, help=f"Style number from 001 to {max_num:03}")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--mode", default="pure-image", choices=["pure-image", "graphic-text"])
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model or model family to resolve capability against")
    parser.add_argument("--ratio")
    parser.add_argument("--subject")
    parser.add_argument("--text")
    args = parser.parse_args()
    try:
        val = int(args.style)
        if not 1 <= val <= max_num:
            raise ValueError()
        number = f"{val:03}"
    except (ValueError, TypeError) as exc:
        raise SystemExit(f"Style must be a number from 001 to {max_num:03}.") from exc
    selected = next((item for item in styles if item["number"] == number), None)
    if selected is None:
        raise SystemExit(f"Style must be a number from 001 to {max_num:03}.")

    gen = selected["generation_name"]
    reference = selected["reference"]
    decision = resolve(args.model, number)
    traits = positive_traits(selected.get("traits", "")) if decision["include_prompt_traits"] else ""
    use_ref = decision["use_reference_image"]
    reference_path = decision["reference_path"]

    extra_zh = "；".join(filter(None, [f"画幅：{args.ratio}" if args.ratio else "",
                                       f"主体限制：{args.subject}" if args.subject else "",
                                       f"文字要求：{args.text}" if args.text else ""]))
    extra_en = "; ".join(filter(None, [f"aspect ratio: {args.ratio}" if args.ratio else "",
                                       f"subject constraints: {args.subject}" if args.subject else "",
                                       f"text requirement: {args.text}" if args.text else ""]))

    zh, en, shown_reference = build_body(
        number, gen, reference, args.theme, traits, use_ref, reference_path,
        extra_zh, extra_en, args.mode,
    )

    print(f"Selected style: #{number} · {gen}")
    print("\n中文提示词：")
    print(zh)
    print("\nEnglish prompt:")
    print(en)
    if shown_reference:
        # Reference shown outside the copyable prompts (graphic-text mode).
        print(file=sys.stderr)
        print(f"参考图（置于提示词之外，仅供风格参考）：{shown_reference}", file=sys.stderr)
    print("\nPaste either prompt into an image AI; this skill does not generate an image.")


if __name__ == "__main__":
    main()
