import gradio as gr
from PIL import Image, ImageDraw
import traceback

# -----------------------------
# Configuration
# -----------------------------

TARGET_FORMATS = {
    "Square": (1024, 1024),
    "Landscape": (1216, 832),
    "Portrait": (832, 1216),
}

PREVIEW_MAX_SIZE = 500
UPLOAD_HEIGHT = PREVIEW_MAX_SIZE + 20


# -----------------------------
# Core Logic
# -----------------------------

def _compute_overlay_size(preview_w, preview_h, aspect_ratio):
    overlay_w_if_h_is_max = preview_h * aspect_ratio

    if overlay_w_if_h_is_max <= preview_w:
        overlay_h = preview_h
        overlay_w = int(overlay_w_if_h_is_max)
    else:
        overlay_w = preview_w
        overlay_h = int(preview_w / aspect_ratio)

    return max(1, overlay_w), max(1, overlay_h)


def _clamp_center(cx, cy, preview_w, preview_h, overlay_w, overlay_h):
    min_cx = overlay_w / 2
    max_cx = preview_w - overlay_w / 2
    min_cy = overlay_h / 2
    max_cy = preview_h - overlay_h / 2

    if max_cx < min_cx:
        cx = preview_w / 2
    else:
        cx = max(min_cx, min(cx, max_cx))

    if max_cy < min_cy:
        cy = preview_h / 2
    else:
        cy = max(min_cy, min(cy, max_cy))

    return cx, cy


def _movement_step(preview_w, preview_h, overlay_w, overlay_h):
    # Half-step movement for finer control
    step_x = max(3, min(20, overlay_w * 0.03))
    step_y = max(3, min(20, overlay_h * 0.03))

    if overlay_w >= preview_w:
        step_x = 0
    if overlay_h >= preview_h:
        step_y = 0

    return step_x, step_y


def build_images(original_image, format_key, coords):
    target_w, target_h = TARGET_FORMATS[format_key]
    aspect_ratio = target_w / target_h

    preview = original_image.copy()
    preview.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
    pw, ph = preview.size

    overlay_w, overlay_h = _compute_overlay_size(pw, ph, aspect_ratio)

    cx, cy = _clamp_center(coords[0], coords[1], pw, ph, overlay_w, overlay_h)

    x0 = cx - overlay_w / 2
    y0 = cy - overlay_h / 2

    preview_overlay = preview.copy()
    draw = ImageDraw.Draw(preview_overlay)
    draw.rectangle([x0, y0, x0 + overlay_w, y0 + overlay_h], outline="red", width=3)

    scale = original_image.width / pw
    crop = original_image.crop((
        x0 * scale,
        y0 * scale,
        (x0 + overlay_w) * scale,
        (y0 + overlay_h) * scale
    ))

    final = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return preview_overlay, final, (cx, cy)


# -----------------------------
# Event Handlers
# -----------------------------

def load_image(image, format_key):
    if image is None:
        return None, None, None, None

    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
    center = (preview.width / 2, preview.height / 2)

    p, f, c = build_images(image, format_key, center)
    return image, c, p, f


def change_format(image, format_key, coords):
    if image is None:
        return gr.skip(), gr.skip(), gr.skip()

    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))

    if coords is None:
        coords = (preview.width / 2, preview.height / 2)

    p, f, c = build_images(image, format_key, coords)
    return c, p, f


def move_box(image, format_key, coords, direction):
    if image is None:
        return gr.skip(), gr.skip(), gr.skip()

    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
    pw, ph = preview.size

    target_w, target_h = TARGET_FORMATS[format_key]
    aspect_ratio = target_w / target_h
    overlay_w, overlay_h = _compute_overlay_size(pw, ph, aspect_ratio)

    if coords is None:
        coords = (pw / 2, ph / 2)

    cx, cy = _clamp_center(coords[0], coords[1], pw, ph, overlay_w, overlay_h)
    step_x, step_y = _movement_step(pw, ph, overlay_w, overlay_h)

    if direction == "up":
        cy -= step_y
    elif direction == "down":
        cy += step_y
    elif direction == "left":
        cx -= step_x
    elif direction == "right":
        cx += step_x

    cx, cy = _clamp_center(cx, cy, pw, ph, overlay_w, overlay_h)

    p, f, c = build_images(image, format_key, (cx, cy))
    return c, p, f


def center_box(image, format_key, coords):
    if image is None:
        return gr.skip(), gr.skip(), gr.skip()

    # Center in preview space so it matches what the user sees
    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
    pw, ph = preview.size
    center = (pw / 2, ph / 2)

    p, f, c = build_images(image, format_key, center)
    return c, p, f


# -----------------------------
# UI
# -----------------------------

CSS = """
.nav-btn button {
    width: 100%;
    height: 42px;
    font-size: 15px;
}

.nav-placeholder {
    height: 42px;
    visibility: hidden;
}

.nav-row {
    gap: 10px !important;
    margin-top: 6px !important;
    margin-bottom: 6px !important;
}

.nav-row-down {
    margin-top: 14px !important;
}
"""

try:
    with gr.Blocks() as app:
        image_state = gr.State(None)
        coord_state = gr.State(None)

        gr.Markdown("# Image Resizer")
        gr.Markdown("Upload an image. Use directional buttons to move the red crop box.")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Upload Image")
                image_input = gr.Image(type="pil", show_label=False, height=UPLOAD_HEIGHT)

                gr.Markdown("### Output Format")
                format_select = gr.Radio(list(TARGET_FORMATS.keys()), value="Square", show_label=False)

                gr.Markdown("### Nudge Crop Box")

                with gr.Column():
                    # Row 1: [blank] [Up] [blank]
                    with gr.Row(elem_classes=["nav-row"]):
                        with gr.Column(scale=1, min_width=0):
                            gr.HTML('<div class="nav-placeholder"></div>')
                        with gr.Column(scale=1, min_width=0):
                            btn_up = gr.Button("Up", elem_classes=["nav-btn"])
                        with gr.Column(scale=1, min_width=0):
                            gr.HTML('<div class="nav-placeholder"></div>')

                    # Row 2: [Left] [Center] [Right]
                    with gr.Row(elem_classes=["nav-row"]):
                        with gr.Column(scale=1, min_width=0):
                            btn_left = gr.Button("Left", elem_classes=["nav-btn"])
                        with gr.Column(scale=1, min_width=0):
                            btn_center = gr.Button("Center", elem_classes=["nav-btn"])
                        with gr.Column(scale=1, min_width=0):
                            btn_right = gr.Button("Right", elem_classes=["nav-btn"])

                    # Row 3: [blank] [Down] [blank]
                    with gr.Row(elem_classes=["nav-row", "nav-row-down"]):
                        with gr.Column(scale=1, min_width=0):
                            gr.HTML('<div class="nav-placeholder"></div>')
                        with gr.Column(scale=1, min_width=0):
                            btn_down = gr.Button("Down", elem_classes=["nav-btn"])
                        with gr.Column(scale=1, min_width=0):
                            gr.HTML('<div class="nav-placeholder"></div>')

            with gr.Column(scale=2):
                gr.Markdown("### Preview")
                preview_output = gr.Image(show_label=False, height=PREVIEW_MAX_SIZE + 20)

                gr.Markdown("### Final Resized Image")
                final_output = gr.Image(show_label=False)

        # Use upload event like before
        image_input.upload(
            load_image,
            inputs=[image_input, format_select],
            outputs=[image_state, coord_state, preview_output, final_output]
        )

        format_select.change(
            change_format,
            inputs=[image_state, format_select, coord_state],
            outputs=[coord_state, preview_output, final_output]
        )

        common_inputs = [image_state, format_select, coord_state]

        btn_up.click(lambda i, f, c: move_box(i, f, c, "up"),
                     inputs=common_inputs,
                     outputs=[coord_state, preview_output, final_output])

        btn_down.click(lambda i, f, c: move_box(i, f, c, "down"),
                       inputs=common_inputs,
                       outputs=[coord_state, preview_output, final_output])

        btn_left.click(lambda i, f, c: move_box(i, f, c, "left"),
                       inputs=common_inputs,
                       outputs=[coord_state, preview_output, final_output])

        btn_right.click(lambda i, f, c: move_box(i, f, c, "right"),
                        inputs=common_inputs,
                        outputs=[coord_state, preview_output, final_output])

        btn_center.click(lambda i, f, c: center_box(i, f, c),
                         inputs=common_inputs,
                         outputs=[coord_state, preview_output, final_output])

    app.launch(
    server_port=7860,
    share=False,
    theme=gr.themes.Soft(),
    css=CSS
    )

except Exception:
    print("ERROR")
    traceback.print_exc()
    input("Press Enter to exit...")